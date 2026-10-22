#!/usr/bin/env bash
# requires: docker python3 curl
#
# The prompt cache marker across the pinned agentgateway (cache design C2). The harness rewrites
# the SDK's cache_control as prompt_cache_breakpoint (agent-platform#132), the one field 1.6
# converts from Chat Completions to Messages; an agentgateway bump that drops the conversion
# re-prices every internal run about 20x and says nothing. This runs the proxy image
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
docker info >/dev/null 2>&1 || { echo "SKIP: no docker daemon"; exit 77; }

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

ready=""
for _ in $(seq 1 30); do
  if request marked | curl -fsS "http://$gw/v1/chat/completions" -H 'content-type: application/json' -d @- >/dev/null 2>&1; then
    ready=1; break
  fi
  sleep 1
done
[ -n "$ready" ] || { docker logs "$name" 2>&1 | tail -30 >&2; echo "the gateway never answered" >&2; exit 1; }
request control | curl -fsS "http://$gw/v1/chat/completions" -H 'content-type: application/json' -d @- >/dev/null \
  || { echo "the control request failed" >&2; exit 1; }
curl -fsS "http://$stats/metrics" > "$tmp/metrics.txt" || { echo "no metrics on $stats" >&2; exit 1; }

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
    # The gateway puts the marker on the tool result's last content block, not on the tool_result itself.
    inner = results[0].get("content")
    marker = inner[-1].get("cache_control") if isinstance(inner, list) and inner and isinstance(inner[-1], dict) else None
    check(marker == EPHEMERAL, f"the tool result's last content block carries cache_control {EPHEMERAL} and no ttl, got {results[0]}")
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
