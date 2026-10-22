# Cache protection (v3 feature 11, part one) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** An internal run that loses Anthropic's prompt cache is alerted on, and an agentgateway pin
that drops the cache marker fails CI, both proven without a cluster.

**Architecture:** Two alerts and a recording rule on the gateway's per-run token series, plus a log
rule on the harness's "NOT applied" line. Two offline suites prove them: `promtool test rules` on
synthetic series, and a container test that runs the pinned agentgateway image against a fake
Anthropic upstream and checks both the Messages body it emits and the token series it exports. The
live drill is deferred to the loop-policy composition release (decision D4, offline first).

**Tech Stack:** VMRule (MetricsQL, PromQL-compatible here; LogsQL), promtool 3.15.0 (mise), Docker,
agentgateway v1.6.0 standalone, Python 3 with PyYAML, Bash suites run by `scripts/ci/run-tests.sh`.

**Spec:** [the prompt cache design](../specs/2026-10-21-prompt-cache-design.md), decisions C1 and C2.
This plan's choices, approved 2026-10-22: the scope is this repository only (the harness's per-step
log moves to the bench); the drill is replaced by offline proofs now and a live drill later.

## Global Constraints

- Work in the worktree `.claude/worktrees/cache-protection`, branch `feat/cache-protection`. Rebase
  onto a freshly fetched `origin/main` before every push.
- `task check` is the evidence (AGENTS.md). On this machine run it as
  `bash $SCRATCH/check.sh <worktree>`, which puts the system `python3` (it has PyYAML) ahead of
  mise's global python.
- Commits: conventional, English, **no trailers**.
- `$SCRATCH` is a scratch directory outside the repository.
- Thresholds, verbatim from C1: `AgentCacheReadShareLow` when "an internal run's share over 15
  minutes is under 60% with at least 200k input tokens in the window"; `AgentCacheReadZero` when "an
  internal run has read nothing after its first 100k input tokens".
- Internal runs are selected by `namespace="agent-gateway"`,
  `ar_agent=~"system:serviceaccount:agents:xplane-run-.+"` and the provider label value Task 1
  confirms (expected `gen_ai_provider_name="anthropic"`). Every rule uses the same selector.
- Every alert carries `runbook_url` and `dashboard` (`test-agent-alert-annotations`). Runbook:
  `https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#part-e--the-cache-read-share`;
  dashboard: `https://grafana.${private_domain_name}/d/agent-gateway`.
- No rule reads another rule's output: vmalert writes recorded series through remote write, so a
  later rule in the same group may not see them yet.
- A suite starts with `# requires: <tools>` on its second line, exits 77 to SKIP, and reads the real
  tree, never copies of it.
- The wire test reads the gateway image from `infrastructure/base/agent-gateway/parameters.yaml`
  (registry, repository, tag, digest), so a pin bump re-runs it on the new image.

## File structure

| File | Change | Responsibility |
|---|---|---|
| `observability/base/agent-platform/vmrule.yaml` | modify: append group `agent-cache` | the share record and the two metric alerts |
| `observability/base/agent-platform/vmrule-logs.yaml` | modify: one rule | `AgentCacheMarkerMissing` |
| `observability/base/agent-platform/grafana-dashboard-agent-gateway.yaml` | modify: panel 12 | the share per internal run |
| `scripts/ci/tests/test-agent-cache-alerts.sh` | create | `promtool test rules` on the `agent-cache` group |
| `scripts/ci/tests/test-agent-gateway-cache-wire.sh` | create | the pinned gateway against a fake Anthropic upstream |
| `scripts/ci/tests/test-agent-observability.py` | modify: one needle | the dashboard reads the share |
| `docs/runbooks/agent-factory/04-gateway-secrets-budgets.md` | modify: Part E | what each alert means and what to do |
| `website/content/docs/platform/ai-platform/observability.md` | modify: alert table | the three alerts |
| `website/content/docs/platform/ai-platform/agents/harness.md` | modify: one row | the alert beside the log line |
| `docs/superpowers/specs/2026-10-21-prompt-cache-design.md` | modify: status, gate 1 | the amendment |

---

### Task 1: Spike: the standalone gateway path (throwaway)

Establishes five facts the next tasks depend on. Nothing from this task is committed; its findings
are written into Task 2's rules and Task 3's suite.

**Files:** none in the repository. Work in `$SCRATCH/spike-wire/`.

**Prerequisite:** a running Docker daemon. On this machine it is installed but stopped: the owner
runs `! sudo systemctl start docker`.

| Fact | Question |
|---|---|
| F1 | A standalone config that routes `/v1/chat/completions` (Completions) to the Anthropic provider at a host override, over plain HTTP or, failing that, TLS with verification off |
| F2 | Where `cache_control` lands in the emitted Messages body: the system block, and the block of the last `tool_result` (on the `tool_result` itself or on its last content block) |
| F3 | Whether the `input` token series includes cache reads and writes (Chat Completions semantics) or excludes them (Anthropic's `input_tokens`) |
| F4 | The label carrying the provider (`gen_ai_system` before the scrape's relabel) and its value for the Anthropic provider; whether `gen_ai_request_model` holds the alias or the resolved model |
| F5 | The metrics address in standalone mode (expected `:15020/metrics`) |

- [ ] **Step 1: Pull the image and read its flags and schema**

```bash
mkdir -p $SCRATCH/spike-wire && cd $SCRATCH/spike-wire
IMG=cr.agentgateway.dev/agentgateway:v1.6.0@sha256:9d3e6044ddcdc0878b1787f77bd401252b95e22684203fb5e874c4c42d2ed90c
docker pull "$IMG"
docker run --rm "$IMG" --help
curl -fsSL https://agentgateway.dev/schema/config -o schema.json
python3 -c 'import json,sys; s=open("schema.json").read(); [print(k, k in s) for k in ("hostOverride","statsAddr","modelAliases","backendTLS","insecure")]'
```

Expected: `-f` takes a config file; each key prints `True`. A key that prints `False` names the field
to look up in `schema.json` before Step 3.

- [ ] **Step 2: Write the fake upstream**

`$SCRATCH/spike-wire/fake.py` (Task 3 embeds the same file):

```python
"""Stands in for api.anthropic.com: records each request, answers one Messages reply with cache usage."""
import http.server
import json
import sys

PORT, OUT = int(sys.argv[1]), sys.argv[2]
REPLY = json.dumps({
    "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
    "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "stop_sequence": None,
    "usage": {"input_tokens": 100, "output_tokens": 10,
              "cache_read_input_tokens": 900, "cache_creation_input_tokens": 50},
}).encode()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        with open(OUT, "a") as f:
            f.write(json.dumps({"path": self.path, "body": json.loads(body)}) + "\n")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(REPLY)))
        self.end_headers()
        self.wfile.write(REPLY)

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
```

- [ ] **Step 3: Write the first config attempt**

`$SCRATCH/spike-wire/config.yaml`:

```yaml
# yaml-language-server: $schema=https://agentgateway.dev/schema/config
config:
  statsAddr: 0.0.0.0:15020
binds:
- port: 3000
  listeners:
  - protocol: HTTP
    routes:
    - name: models
      matches:
      - path:
          pathPrefix: /v1
      policies:
        ai:
          routes:
            /v1/chat/completions: completions
            /v1/messages: messages
          modelAliases:
            agent-default: claude-opus-5-5
            tier-light: claude-haiku-5-5
        backendAuth:
          key: test-key
      backends:
      - ai:
          name: anthropic
          provider:
            anthropic: {}
          hostOverride: host.docker.internal:18080
```

- [ ] **Step 4: Run both and send one marked request**

```bash
python3 fake.py 18080 bodies.jsonl & echo $! > fake.pid
docker run -d --rm --name agw-spike --add-host=host.docker.internal:host-gateway \
  -v "$PWD/config.yaml:/config.yaml:ro" -p 127.0.0.1:13000:3000 -p 127.0.0.1:15020:15020 "$IMG" -f /config.yaml
sleep 3; docker logs agw-spike 2>&1 | tail -20
curl -sS localhost:13000/v1/chat/completions -H 'content-type: application/json' -d '{
  "model": "agent-default", "max_tokens": 64,
  "messages": [
    {"role": "system", "content": [{"type": "text", "text": "You are a test.", "prompt_cache_breakpoint": {"mode": "explicit"}}]},
    {"role": "user", "content": "list the files"},
    {"role": "assistant", "content": null, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "terminal", "arguments": "{\"command\": \"ls\"}"}}]},
    {"role": "tool", "tool_call_id": "call_1", "content": [{"type": "text", "text": "README.md", "prompt_cache_breakpoint": {"mode": "explicit"}}]}
  ],
  "tools": [{"type": "function", "function": {"name": "terminal", "description": "run a command", "parameters": {"type": "object", "properties": {"command": {"type": "string"}}}}}]
}'
```

Expected: a Chat Completions reply with `"content": "ok"` and a line in `bodies.jsonl`.

If the config is refused, the log names the field: fix it from `schema.json` and rerun. If the fake
receives nothing and the gateway logs a TLS or connection error, the provider forces TLS: generate a
self-signed pair, serve `fake.py` behind it, and add `policies: {backendTLS: {insecure: true}}` to
the backend:

```bash
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 1 -subj /CN=host.docker.internal
# fake.py: wrap the server socket with ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain("cert.pem", "key.pem")
```

- [ ] **Step 5: Read F2 to F5**

```bash
python3 -m json.tool < <(tail -1 bodies.jsonl)
curl -sS localhost:15020/metrics | grep -E '^agentgateway_gen_ai_client_token_usage_sum'
```

Record:
- F2: the JSON path of each `cache_control` and its exact value (expected `{"type": "ephemeral"}`, no
  `ttl`); the upstream `model` (expected `claude-opus-5-5`).
- F3: the `input` sample after one request. `1050` means input includes reads and writes
  (`100 + 900 + 50`); `100` means it excludes them.
- F4: the provider label and value on the token series; the `gen_ai_request_model` value.
- F5: the address that served the metrics.

- [ ] **Step 6: Clean up**

```bash
docker rm -f agw-spike; kill "$(cat fake.pid)"
```

Write F1 to F5 at the top of the scratchpad directory as `findings.md`. No commit.

Measured 2026-10-22 (Docker was down: the spike ran the checksum-verified v1.6.0 release binary with
`hostOverride: 127.0.0.1:<port>`):

- F1: plain HTTP to the host override works.
- F2: the marker lands at `system[0].cache_control` and on the tool result's last content block.
- F3: `input` includes cache reads and writes, streaming and non-streaming.
- F4: `gen_ai_system="anthropic"`; the request model is the resolved one.
- F5: metrics on `:15020`.

---

### Task 2: The `agent-cache` rules and their unit test

**Files:**
- Create: `scripts/ci/tests/test-agent-cache-alerts.sh`
- Modify: `observability/base/agent-platform/vmrule.yaml` (append a group after `agent-gateway`)

**Interfaces:**
- Consumes: F3 (the denominator), F4 (the provider selector) from Task 1.
- Produces: the record `agent_run:cache_read_share:ratio15m` (labels: `ar_agent`), read by Task 4's
  panel; the alerts `AgentCacheReadZero` (severity `critical`) and `AgentCacheReadShareLow`
  (severity `warning`), named in Task 4's docs.

The series below assume F3 = inclusive and F4 = `gen_ai_provider_name="anthropic"`. If F3 is
exclusive, every `INPUT` in the rules becomes the sum of the three input types
(`gen_ai_token_type=~"input|cached_input|cache_creation_input"`), and in the test each run's `input`
series counts only the uncached part (subtract its `cached_input` increments). If F4 differs, replace
the selector everywhere.

- [ ] **Step 1: Write the failing test**

`scripts/ci/tests/test-agent-cache-alerts.sh`:

```bash
#!/usr/bin/env bash
# requires: promtool python3
#
# The prompt cache alerts (cache design C1), evaluated by promtool on synthetic series shaped as
# the agent router's scrape leaves them (vmpodscrape.yaml). A dropped marker fires
# AgentCacheReadZero within two scrapes of a run's first 100k input tokens; a share under 60% over
# 15 minutes fires AgentCacheReadShareLow only with 200k input tokens in the window, so one
# condensation does not; public runs (Z.ai) are never selected. Annotations are stripped from the
# copy promtool reads: it compares them exactly, and test-agent-alert-annotations owns them.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

ROOT="$ROOT" OUT="$tmp/rules.yaml" python3 - <<'PY' || exit 1
import os
import sys
import yaml

path = os.path.join(os.environ["ROOT"], "observability/base/agent-platform/vmrule.yaml")
groups = [g for d in yaml.safe_load_all(open(path)) if d and d.get("kind") == "VMRule"
          for g in d["spec"]["groups"] if g["name"] == "agent-cache"]
if not groups:
    sys.exit("no group agent-cache in observability/base/agent-platform/vmrule.yaml")
for rule in groups[0]["rules"]:
    rule.pop("annotations", None)
yaml.safe_dump({"groups": [{"name": "agent-cache", "rules": groups[0]["rules"]}]},
               open(os.environ["OUT"], "w"), sort_keys=False)
PY

S='gen_ai_client_token_usage_sum{namespace="agent-gateway", gen_ai_provider_name="anthropic", ar_agent="system:serviceaccount:agents:xplane-run-'
cat > "$tmp/tests.yaml" <<EOF
rule_files: [rules.yaml]
evaluation_interval: 30s
tests:
  # A dropped marker: input grows 20k a scrape, nothing is ever read.
  - interval: 30s
    input_series:
      - series: '${S}zero", gen_ai_token_type="input"}'
        values: '0+20000x40'
    alert_rule_test:
      - {eval_time: 2m, alertname: AgentCacheReadZero, exp_alerts: []}
      - eval_time: 3m
        alertname: AgentCacheReadZero
        exp_alerts:
          - exp_labels: {severity: critical, ar_agent: "system:serviceaccount:agents:xplane-run-zero"}
      - eval_time: 16m
        alertname: AgentCacheReadShareLow
        exp_alerts:
          - exp_labels: {severity: warning, ar_agent: "system:serviceaccount:agents:xplane-run-zero"}
  # A dropped marker whose cached_input series exists at zero (Anthropic answers
  # cache_read_input_tokens: 0 on every reply): the same alerts fire as for an absent series.
  - interval: 30s
    input_series:
      - series: '${S}zeroseries", gen_ai_token_type="input"}'
        values: '0+20000x40'
      - series: '${S}zeroseries", gen_ai_token_type="cached_input"}'
        values: '0x40'
    alert_rule_test:
      - eval_time: 3m
        alertname: AgentCacheReadZero
        exp_alerts:
          - exp_labels: {severity: critical, ar_agent: "system:serviceaccount:agents:xplane-run-zeroseries"}
      - eval_time: 16m
        alertname: AgentCacheReadShareLow
        exp_alerts:
          - exp_labels: {severity: warning, ar_agent: "system:serviceaccount:agents:xplane-run-zeroseries"}
  # A run that dropped its marker and then ended: input reaches 120k and stays flat (the gateway
  # keeps exporting the series). It fires at 3m; at 20m the 15m window (5m-20m) holds no increase,
  # so the alert has resolved.
  - interval: 30s
    input_series:
      - series: '${S}ended", gen_ai_token_type="input"}'
        values: '0+20000x6 120000x40'
    alert_rule_test:
      - eval_time: 3m
        alertname: AgentCacheReadZero
        exp_alerts:
          - exp_labels: {severity: critical, ar_agent: "system:serviceaccount:agents:xplane-run-ended"}
      - {eval_time: 20m, alertname: AgentCacheReadZero, exp_alerts: []}
  # A healthy run: 90% read. Neither fires.
  - interval: 30s
    input_series:
      - series: '${S}ok", gen_ai_token_type="input"}'
        values: '0+20000x40'
      - series: '${S}ok", gen_ai_token_type="cached_input"}'
        values: '0+18000x40'
    alert_rule_test:
      - {eval_time: 3m, alertname: AgentCacheReadZero, exp_alerts: []}
      - {eval_time: 16m, alertname: AgentCacheReadShareLow, exp_alerts: []}
    promql_expr_test:
      - expr: agent_run:cache_read_share:ratio15m
        eval_time: 16m
        exp_samples:
          - labels: 'agent_run:cache_read_share:ratio15m{ar_agent="system:serviceaccount:agents:xplane-run-ok"}'
            value: 0.9
  # A gradual loss: 50% read on 600k input over 15 minutes.
  - interval: 30s
    input_series:
      - series: '${S}half", gen_ai_token_type="input"}'
        values: '0+20000x40'
      - series: '${S}half", gen_ai_token_type="cached_input"}'
        values: '0+10000x40'
    alert_rule_test:
      - {eval_time: 3m, alertname: AgentCacheReadZero, exp_alerts: []}
      - eval_time: 16m
        alertname: AgentCacheReadShareLow
        exp_alerts:
          - exp_labels: {severity: warning, ar_agent: "system:serviceaccount:agents:xplane-run-half"}
  # The same 50% on 90k input in the window (a condensation in a quiet run): under the volume floor.
  - interval: 30s
    input_series:
      - series: '${S}quiet", gen_ai_token_type="input"}'
        values: '0+3000x40'
      - series: '${S}quiet", gen_ai_token_type="cached_input"}'
        values: '0+1500x40'
    alert_rule_test:
      - {eval_time: 16m, alertname: AgentCacheReadShareLow, exp_alerts: []}
  # A public run on Z.ai reads nothing explicit: never selected.
  - interval: 30s
    input_series:
      - series: 'gen_ai_client_token_usage_sum{namespace="agent-gateway", gen_ai_provider_name="custom", ar_agent="system:serviceaccount:agents:xplane-run-public", gen_ai_token_type="input"}'
        values: '0+20000x40'
    alert_rule_test:
      - {eval_time: 3m, alertname: AgentCacheReadZero, exp_alerts: []}
      - {eval_time: 16m, alertname: AgentCacheReadShareLow, exp_alerts: []}
EOF

cd "$tmp" && promtool test rules tests.yaml
```

- [ ] **Step 2: Run it and watch it fail**

```bash
chmod +x scripts/ci/tests/test-agent-cache-alerts.sh
bash scripts/ci/tests/test-agent-cache-alerts.sh; echo "exit=$?"
```

Expected: `no group agent-cache in observability/base/agent-platform/vmrule.yaml`, `exit=1`.

- [ ] **Step 3: Append the group to `vmrule.yaml`**

At the end of the file, at the indentation of `- name: agent-gateway`:

```yaml
    # Prompt caching on internal runs (cache design C1): a dropped marker re-prices every step about
    # 20x and only the harness log would say so. The series carry a run (ar_agent) but no step; the
    # per-step view is the harness log's. No rule reads another's output: vmalert's recorded series
    # reach the datasource through remote write, too late for the same evaluation.
    - name: agent-cache
      rules:
        - record: agent_run:cache_read_share:ratio15m
          expr: (sum by (ar_agent) (increase(gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent=~"system:serviceaccount:agents:xplane-run-.+", gen_ai_provider_name="anthropic", gen_ai_token_type="cached_input"}[15m])) or sum by (ar_agent) (increase(gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent=~"system:serviceaccount:agents:xplane-run-.+", gen_ai_provider_name="anthropic", gen_ai_token_type="input"}[15m])) * 0) / sum by (ar_agent) (increase(gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent=~"system:serviceaccount:agents:xplane-run-.+", gen_ai_provider_name="anthropic", gen_ai_token_type="input"}[15m]))
        - alert: AgentCacheReadZero
          expr: sum by (ar_agent) (gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent=~"system:serviceaccount:agents:xplane-run-.+", gen_ai_provider_name="anthropic", gen_ai_token_type="input"}) >= 100000 unless on (ar_agent) sum by (ar_agent) (gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent=~"system:serviceaccount:agents:xplane-run-.+", gen_ai_provider_name="anthropic", gen_ai_token_type="cached_input"}) > 0 and on (ar_agent) sum by (ar_agent) (increase(gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent=~"system:serviceaccount:agents:xplane-run-.+", gen_ai_provider_name="anthropic", gen_ai_token_type="input"}[15m])) > 0
          labels:
            severity: critical
          annotations:
            summary: "{{ $labels.ar_agent }} read nothing from Anthropic's prompt cache in its first {{ $value | humanize }} input tokens"
            description: "Every step pays the full input price, about 20x a cached one. A gateway or harness bump dropped the cache marker: read the run's log for 'prompt cache NOT applied' and the last change to infrastructure/base/agent-gateway/parameters.yaml. A long run can be stopped: kubectl annotate agentrun -n agents <name> agents.ogenki.io/revoked=budget-run"
            runbook_url: "https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#part-e--the-cache-read-share"
            dashboard: "https://grafana.${private_domain_name}/d/agent-gateway"
        - alert: AgentCacheReadShareLow
          expr: (sum by (ar_agent) (increase(gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent=~"system:serviceaccount:agents:xplane-run-.+", gen_ai_provider_name="anthropic", gen_ai_token_type="cached_input"}[15m])) or sum by (ar_agent) (increase(gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent=~"system:serviceaccount:agents:xplane-run-.+", gen_ai_provider_name="anthropic", gen_ai_token_type="input"}[15m])) * 0) / sum by (ar_agent) (increase(gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent=~"system:serviceaccount:agents:xplane-run-.+", gen_ai_provider_name="anthropic", gen_ai_token_type="input"}[15m])) < 0.6 and on (ar_agent) sum by (ar_agent) (increase(gen_ai_client_token_usage_sum{namespace="agent-gateway", ar_agent=~"system:serviceaccount:agents:xplane-run-.+", gen_ai_provider_name="anthropic", gen_ai_token_type="input"}[15m])) >= 200000
          labels:
            severity: warning
          annotations:
            summary: "{{ $labels.ar_agent }} read {{ $value | humanizePercentage }} of its input from the prompt cache over 15 minutes"
            description: "Healthy internal runs read about 85%. One condensation or a resume dips the share for one window; a share that stays low is the tool list changing mid-run (a federated MCP target dropped and re-added) or something dynamic in the prompt. The run dashboard's steps show which."
            runbook_url: "https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#part-e--the-cache-read-share"
            dashboard: "https://grafana.${private_domain_name}/d/agent-gateway"
```

- [ ] **Step 4: Run the test and promtool's syntax check**

```bash
bash scripts/ci/tests/test-agent-cache-alerts.sh; echo "exit=$?"
bash scripts/ci/tests/test-agent-alert-annotations.sh
```

Expected: `SUCCESS` from promtool and `exit=0`; the annotation suite prints `PASS`. If the only
failure is the share's `exp_samples` reading `0.8999999…` against `0.9`, the expression is right:
write the value promtool printed.

- [ ] **Step 5: Commit**

```bash
git add scripts/ci/tests/test-agent-cache-alerts.sh observability/base/agent-platform/vmrule.yaml
git commit -m "feat(observability): alert when an internal run loses its prompt cache"
```

---

### Task 3: The gateway wire test

**Files:**
- Create: `scripts/ci/tests/test-agent-gateway-cache-wire.sh`

**Interfaces:**
- Consumes: F1 (config shape), F2 (marker paths), F3 and F4 (series) from Task 1;
  `infrastructure/base/agent-gateway/parameters.yaml` (image) and `anthropic.yaml` (aliases, routes).
- Produces: nothing later tasks call; Task 4's runbook names the suite.

The config below is Task 1's expected F1. If the spike needed a different shape (field names, TLS),
the `render` step writes that shape instead; the assertions do not change. The F2 paths asserted
below are the expected ones; set them to what Task 1 recorded.

- [ ] **Step 1: Write the suite**

`scripts/ci/tests/test-agent-gateway-cache-wire.sh`:

```bash
#!/usr/bin/env bash
# requires: docker python3 curl
#
# The prompt cache marker across the pinned agentgateway (cache design C2). The harness rewrites
# the SDK's cache_control as prompt_cache_breakpoint (agent-platform#132), the one field 1.6
# converts from Chat Completions to Messages; an agentgateway bump that drops the conversion
# makes every internal run cost about 4x as much (an input token 20x) and says nothing. This runs the proxy image
# parameters.yaml pins, standalone, with anthropic.yaml's aliases and routes, against a fake
# Anthropic upstream, and checks the Messages body it emits and the token series it exports, which
# the agent-cache alerts read. A control request without the markers proves the check can fail.
# Standalone proves the conversion code, not the controller's translation of the CRDs.
# With hostOverride set the upstream request keeps the client's path (/v1/chat/completions) while its
# body is Messages; the fake answers any path, so nothing here depends on it.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
if ! docker info >/dev/null 2>&1; then
  if [ "${CI:-}" = "true" ]; then
    echo "FAIL  no docker daemon in CI: the wire test is gate 2 of the cache design and must run here"; exit 1
  fi
  echo "SKIP: no docker daemon"; exit 77
fi

tmp="$(mktemp -d)"
name="agent-gateway-cache-wire-$$"
fake_pid=""
trap 'docker rm -f "$name" >/dev/null 2>&1; [ -n "$fake_pid" ] && kill "$fake_pid" 2>/dev/null; rm -rf "$tmp"' EXIT

port="$(python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1])')"

cat > "$tmp/fake.py" <<'PY'
"""Stands in for api.anthropic.com: records each request, answers one Messages reply with cache usage."""
import http.server
import json
import sys

PORT, OUT = int(sys.argv[1]), sys.argv[2]
REPLY = json.dumps({
    "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
    "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "stop_sequence": None,
    "usage": {"input_tokens": 100, "output_tokens": 10,
              "cache_read_input_tokens": 900, "cache_creation_input_tokens": 50},
}).encode()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        with open(OUT, "a") as f:
            f.write(json.dumps({"path": self.path, "body": json.loads(body)}) + "\n")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(REPLY)))
        self.end_headers()
        self.wfile.write(REPLY)

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
PY
python3 "$tmp/fake.py" "$port" "$tmp/bodies.jsonl" & fake_pid=$!

image="$(ROOT="$ROOT" PORT="$port" OUT="$tmp/config.yaml" python3 - <<'PY'
import os
import yaml

root = os.environ["ROOT"]
params = next(d for d in yaml.safe_load_all(open(f"{root}/infrastructure/base/agent-gateway/parameters.yaml"))
              if d and d["kind"] == "AgentgatewayParameters")["spec"]["image"]
backend = next(d for d in yaml.safe_load_all(open(f"{root}/infrastructure/base/agent-gateway/anthropic.yaml"))
               if d and d["kind"] == "AgentgatewayBackend")["spec"]["policies"]["ai"]
config = {
    "config": {"statsAddr": "0.0.0.0:15020"},
    "binds": [{"port": 3000, "listeners": [{"protocol": "HTTP", "routes": [{
        "name": "models",
        "matches": [{"path": {"pathPrefix": "/v1"}}],
        "policies": {
            "ai": {"routes": {path: kind.lower() for path, kind in backend["routes"].items()},
                   "modelAliases": backend["modelAliases"]},
            "backendAuth": {"key": "test-key"},
        },
        # The gateway resolves this name from the /etc/hosts entry --add-host writes (proven against
        # the v1.6.0 binary with an /etc/hosts-only name).
        "backends": [{"ai": {"name": "anthropic", "provider": {"anthropic": {}},
                             "hostOverride": "host.docker.internal:%s" % os.environ["PORT"]}}],
    }]}]}],
}
yaml.safe_dump(config, open(os.environ["OUT"], "w"), sort_keys=False)
print("%s/%s:%s@%s" % (params["registry"], params["repository"], params["tag"], params["digest"]))
PY
)" || { echo "cannot render the gateway config" >&2; exit 1; }

docker run -d --name "$name" --add-host=host.docker.internal:host-gateway \
  -v "$tmp/config.yaml:/config.yaml:ro" -p 127.0.0.1::3000 -p 127.0.0.1::15020 \
  "$image" -f /config.yaml >/dev/null || { echo "cannot start $image" >&2; exit 1; }
gw="$(docker port "$name" 3000/tcp | head -1)"
stats="$(docker port "$name" 15020/tcp | head -1)"

request() {  # $1: "marked" or "control"
  MODE="$1" python3 - <<'PY'
import json
import os

bp = {"prompt_cache_breakpoint": {"mode": "explicit"}} if os.environ["MODE"] == "marked" else {}
print(json.dumps({
    "model": "agent-default", "max_tokens": 64,
    "messages": [
        {"role": "system", "content": [{"type": "text", "text": "You are a test.", **bp}]},
        {"role": "user", "content": "list the files"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": "call_1", "type": "function",
            "function": {"name": "terminal", "arguments": "{\"command\": \"ls\"}"}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": [{"type": "text", "text": "README.md", **bp}]},
    ],
    "tools": [{"type": "function", "function": {"name": "terminal", "description": "run a command",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}}}}],
}))
PY
}

ready=""; code=""
for _ in $(seq 1 30); do
  if [ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null)" != "true" ]; then
    docker logs "$name" 2>&1 | tail -30 >&2; echo "the gateway container exited before it answered" >&2; exit 1
  fi
  code="$(request marked | curl -sS --max-time 10 -o /dev/null -w '%{http_code}' "http://$gw/v1/chat/completions" -H 'content-type: application/json' -d @- 2>"$tmp/curl.err")"
  if [ "$code" = "200" ]; then ready=1; break; fi
  sleep 1
done
[ -n "$ready" ] || { docker logs "$name" 2>&1 | tail -30 >&2; echo "the gateway never answered: last status ${code:-none}, curl: $(cat "$tmp/curl.err")" >&2; exit 1; }
request control | curl -fsS --max-time 10 "http://$gw/v1/chat/completions" -H 'content-type: application/json' -d @- >/dev/null \
  || { echo "the control request failed" >&2; exit 1; }
curl -fsS --max-time 10 "http://$stats/metrics" > "$tmp/metrics.txt" || { echo "no metrics on $stats" >&2; exit 1; }

BODIES="$tmp/bodies.jsonl" METRICS="$tmp/metrics.txt" ROOT="$ROOT" python3 - <<'PY'
import json
import os
import re
import sys

import yaml

fails = []
def check(ok, message):
    if not ok:
        fails.append(message)

aliases = next(d for d in yaml.safe_load_all(open(os.path.join(os.environ["ROOT"], "infrastructure/base/agent-gateway/anthropic.yaml")))
               if d and d["kind"] == "AgentgatewayBackend")["spec"]["policies"]["ai"]["modelAliases"]
bodies = [json.loads(line)["body"] for line in open(os.environ["BODIES"])]
# The readiness loop resends the marked request until the gateway answers: the control is last.
check(len(bodies) >= 2, f"the fake upstream received {len(bodies)} requests, want at least 2 (marked, control)")
marked, control = bodies[-2], bodies[-1]
n = len(bodies)
EPHEMERAL = {"type": "ephemeral"}

check(marked.get("model") == aliases["agent-default"],
      f"agent-default resolves to {aliases['agent-default']}, got {marked.get('model')}")
system = marked.get("system")
check(isinstance(system, list) and system and system[0].get("cache_control") == EPHEMERAL,
      f"system[0] carries cache_control {EPHEMERAL} and no ttl (C3 changes this), got {system}")
last = marked["messages"][-1]
results = [b for b in last.get("content", []) if isinstance(b, dict) and b.get("type") == "tool_result"]
check(last.get("role") == "user" and results, f"the last message holds the tool result, got {last}")
if results:
    # Either is a valid Anthropic breakpoint: on the tool_result block itself or on its last content block
    # (1.6 measured: the latter).
    result = results[-1]
    inner = result.get("content")
    on_block = inner[-1].get("cache_control") if isinstance(inner, list) and inner and isinstance(inner[-1], dict) else None
    check(EPHEMERAL in (result.get("cache_control"), on_block),
          f"the last tool result carries cache_control {EPHEMERAL} and no ttl, on itself or on its last content block, got {result}")
check("cache_control" not in json.dumps(control),
      "a request without prompt_cache_breakpoint carries no cache_control: the check can fail")

usage = {}
for line in open(os.environ["METRICS"]):
    if line.startswith("agentgateway_gen_ai_client_token_usage_sum{"):
        labels = dict(re.findall(r'(\w+)="([^"]*)"', line.split("}")[0]))
        usage[labels.get("gen_ai_token_type")] = usage.get(labels.get("gen_ai_token_type"), 0) + float(line.rsplit(" ", 1)[1])
        check(labels.get("gen_ai_system") == "anthropic",
              f"the token series name the provider gen_ai_system=anthropic, which the alerts select after the relabel, got {labels}")
check({"input", "output", "input_cache_read", "input_cache_write"} <= set(usage),
      f"the token types vmpodscrape.yaml relabels exist, got {sorted(usage)}")
# Each reply reports input 100, cache read 900, cache write 50: the agent-cache rules divide reads by
# input, which holds only while input counts the cached tokens too.
check(usage.get("input_cache_read") == 900 * n and usage.get("input") == 1050 * n,
      f"over {n} replies, input includes cache reads and writes ({n} x 1050) and reads are {n} x 900, as agent-cache's share assumes, got {usage}")

if fails:
    print("\n".join("FAIL  " + f for f in fails), file=sys.stderr)
    sys.exit(1)
print("PASS")
PY
```

Adjust from Task 1's findings before running: the config keys (F1), the marker path (F2), the
`input` equation (F3: with exclusive semantics assert `input == 100 * n` and say the rules divide by
the three input types), the provider label and value (F4), the port (F5).

- [ ] **Step 2: Run it**

```bash
chmod +x scripts/ci/tests/test-agent-gateway-cache-wire.sh
bash scripts/ci/tests/test-agent-gateway-cache-wire.sh; echo "exit=$?"
```

Expected: `PASS`, `exit=0` (with the Docker daemon running).

- [ ] **Step 3: Prove it can fail on the marker**

Temporarily change the `request marked` call's mode to `control` (both requests unmarked) and rerun.
Expected: `FAIL  system[0] carries cache_control …`, `exit=1`. Restore it.

- [ ] **Step 4: Commit**

```bash
git add scripts/ci/tests/test-agent-gateway-cache-wire.sh
git commit -m "test(agent-gateway): the prompt cache marker across the pinned proxy"
```

---

### Task 4: The log rule, the panel and the docs

**Files:**
- Modify: `observability/base/agent-platform/vmrule-logs.yaml` (after `OctoStsExchangeFailures`)
- Modify: `observability/base/agent-platform/grafana-dashboard-agent-gateway.yaml` (panel 12)
- Modify: `scripts/ci/tests/test-agent-observability.py` (`check_agentgateway_dashboards`)
- Modify: `docs/runbooks/agent-factory/04-gateway-secrets-budgets.md`
- Modify: `website/content/docs/platform/ai-platform/observability.md`
- Modify: `website/content/docs/platform/ai-platform/agents/harness.md`
- Modify: `docs/superpowers/specs/2026-10-21-prompt-cache-design.md`

**Interfaces:**
- Consumes: `agent_run:cache_read_share:ratio15m`, `AgentCacheReadZero`, `AgentCacheReadShareLow`
  (Task 2); the two suites' names (Tasks 2 and 3).

- [ ] **Step 1: Make the dashboard check fail**

In `check_agentgateway_dashboards`, add the record to the needles:

```python
    for needle in ("agentgateway_requests_total", 'status=~\\"5..\\"', "error_type", "gen_ai_server_request_duration_seconds_bucket",
                   "gen_ai_client_token_usage_sum", "ratelimit_service_rate_limit_shadow_mode", "agentgateway_mcp_requests_total",
                   "agent_run:cache_read_share:ratio15m"):
```

Run: `python3 scripts/ci/tests/test-agent-observability.py`
Expected: a failure naming `agent_run:cache_read_share:ratio15m`.

- [ ] **Step 2: Add panel 12**

After the access-log panel (id 11, ending at `y: 40`), add a comma to panel 11's closing `}` and:

```json
        {"id": 12, "type": "timeseries", "title": "Prompt cache: share of input read, per internal run",
         "description": "Under 60% with 200k input in 15 minutes fires AgentCacheReadShareLow; a run at 0 fires AgentCacheReadZero. One condensation or a resume dips one window.",
         "gridPos": {"x": 0, "y": 40, "w": 24, "h": 8},
         "datasource": {"type": "prometheus", "uid": "$${datasource}"},
         "fieldConfig": {"defaults": {"unit": "percentunit", "min": 0, "max": 1}},
         "targets": [{"refId": "A", "legendFormat": "{{ar_agent}}", "expr": "agent_run:cache_read_share:ratio15m"}]}
```

Run: `python3 scripts/ci/tests/test-agent-observability.py`
Expected: no output, exit 0.

- [ ] **Step 3: Add the log rule**

In `vmrule-logs.yaml`, after `OctoStsExchangeFailures`:

```yaml
        # The SDK-shape failure only (cache design C1): the harness could not patch the SDK's model
        # call, so it sends no cache marker at all. AgentCacheReadZero catches the same loss from
        # the gateway side, and also a gateway that drops the marker, which logs nothing.
        - alert: AgentCacheMarkerMissing
          expr: 'kubernetes.pod_namespace:"agents" AND kubernetes.pod_name:xplane-run-* AND _msg:"prompt cache NOT applied" | stats count() as lines | filter lines:>0'
          labels:
            severity: warning
          annotations:
            summary: "A run's harness logged 'prompt cache NOT applied': internal runs pay the full input price on every step"
            description: "An OpenHands SDK upgrade moved the method the harness patches (images/agent-harness/site/sitecustomize.py in agent-platform). Roll the harness pin back, then fix the patch."
            runbook_url: "https://github.com/Smana/ai-native-ref/blob/main/docs/runbooks/agent-factory/04-gateway-secrets-budgets.md#part-e--the-cache-read-share"
            dashboard: "https://grafana.${private_domain_name}/d/agent-gateway"
```

- [ ] **Step 4: Runbook 04, Part E**

Append before `## Results`:

```markdown
## Part E — the cache-read share

Internal runs read about 85% of their input from Anthropic's prompt cache; a step that reads
nothing costs about 20× one that does. The marker that makes it work crosses two repositories: the
harness rewrites the SDK's `cache_control` as `prompt_cache_breakpoint`, and agentgateway converts it
back on the way to Anthropic ([cache design](../../superpowers/specs/2026-10-21-prompt-cache-design.md)).

| Alert | Means | Do |
|---|---|---|
| `AgentCacheReadZero` (critical) | An internal run read nothing after 100k input tokens | Read the run's log for `prompt cache NOT applied`. None: the gateway dropped the marker; check the last change to `infrastructure/base/agent-gateway/parameters.yaml` and roll it back. Stop a long run: `kubectl annotate agentrun -n agents <name> agents.ogenki.io/revoked=budget-run` |
| `AgentCacheReadShareLow` | Under 60% over 15 minutes, with 200k input in the window | One window after a condensation or a resume is expected. If it stays low, read the run's MCP tool lists: a federated target that fails is dropped from the list and re-added, and each change rewrites the cache |
| `AgentCacheMarkerMissing` | The harness could not patch the SDK | Roll the harness pin back; the patch in agent-platform's `sitecustomize.py` needs the SDK's new method |

Offline, `task check` proves both sides: `test-agent-cache-alerts` evaluates the two metric alerts on
synthetic series, and `test-agent-gateway-cache-wire` runs the pinned agentgateway against a fake
Anthropic upstream and fails if the marker or the token series change.

Live, at the next platform session: the share panel on the agent-gateway dashboard reads above 60%
for internal runs and neither alert fires. The drill (a run that sends no marker, through an
`agents.ogenki.io/cache-drill` annotation) waits for the loop-policy composition release.
```

- [ ] **Step 5: The observability page and the harness page**

In `observability.md`, after the `AgentBudgetRefused` row:

```markdown
| `AgentCacheReadZero` | An internal run read nothing from the prompt cache after 100k input tokens: a dropped cache marker, every step at full price |
| `AgentCacheReadShareLow` | An internal run read under 60% of its input from the cache over 15 minutes, with 200k input in the window |
| `AgentCacheMarkerMissing` | A run's harness logged `prompt cache NOT applied` (a LogsQL rule): the SDK changed under the harness's patch |
```

In `harness.md`, replace the row:

```markdown
| An internal run costs as much as a public one | Prompt caching is off: the harness logs `prompt cache NOT applied` at start |
```

with:

```markdown
| An internal run costs as much as a public one | Prompt caching is off: the harness logs `prompt cache NOT applied` at start, and `AgentCacheReadZero` fires once the run passes 100k input tokens |
```

- [ ] **Step 6: Amend the cache design**

In `2026-10-21-prompt-cache-design.md`, the status line gains:

```markdown
· **Amended 2026-10-22**: C1 and C2 built offline ([plan](../plans/2026-10-22-cache-protection-plan.md)); gate 1's drill moves to the loop-policy composition release
```

and gate 1 becomes:

```markdown
1. Offline, in `task check`: `test-agent-cache-alerts` shows `AgentCacheReadZero` firing within two
   scrapes of a run's first 100k input tokens with no reads and `AgentCacheReadShareLow` at 50% on
   600k input but not on 90k; `test-agent-gateway-cache-wire` shows the pinned gateway's series and
   marker. Live, later: a run started with the `agents.ogenki.io/cache-drill` annotation (a harness
   switch that skips the marker rewrite, mapped by the composition) fires `AgentCacheReadZero`
   within two scrapes; the annotation rides the loop-policy release of the `AgentRun` composition.
   `AgentCacheMarkerMissing` matches the substring both of the harness's messages carry
   (`prompt cache NOT applied`); no agent-platform test asserts that message yet, unlike the
   harness's three other patches, which is a follow-up there.
```

- [ ] **Step 7: Run the affected suites, then commit**

```bash
python3 scripts/ci/tests/test-agent-observability.py && bash scripts/ci/tests/test-agent-alert-annotations.sh
git add observability/base/agent-platform/vmrule-logs.yaml observability/base/agent-platform/grafana-dashboard-agent-gateway.yaml \
  scripts/ci/tests/test-agent-observability.py docs/runbooks/agent-factory/04-gateway-secrets-budgets.md \
  website/content/docs/platform/ai-platform/observability.md website/content/docs/platform/ai-platform/agents/harness.md \
  docs/superpowers/specs/2026-10-21-prompt-cache-design.md
git commit -m "feat(observability): the cache-read share on the gateway dashboard, its runbook and the marker log rule"
```

---

### Task 5: Verify, push, open the pull request

- [ ] **Step 1: The whole check**

```bash
bash $SCRATCH/check.sh "$PWD"
tail -20 $SCRATCH/check-cache-protection.log
```

Expected: `exit=0`; `test-agent-cache-alerts` and `test-agent-gateway-cache-wire` both `PASS` (the
wire test SKIPs only without a Docker daemon, and then CI's run is its evidence).

- [ ] **Step 2: Rebase and push**

```bash
git fetch origin && git rebase origin/main
git push -u origin feat/cache-protection
```

- [ ] **Step 3: Open the pull request**

Title: `feat(observability): protect the prompt cache: share alerts and a gateway wire test`. Body in
English: the outcome (C1, C2 offline), the two suites and what each proves, the deferred live drill,
the `task check` summary, and a test plan. No attribution line.
