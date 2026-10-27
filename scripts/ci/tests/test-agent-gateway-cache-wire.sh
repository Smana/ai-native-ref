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
# A last request streams (truthful costs TC4): its reply must be counted as the others are, input
# including the cache reads and writes, which llm_gateway:charge_usd_per_mtoken's join rests on.
# The same proxy prices what it counts (cost cross-check XC1, offline proof 2): it loads the overlay
# model-catalog.yaml renders (gen-prices.py) as its catalog, and agentgateway_gen_ai_client_cost_usd_total
# must read the expected cost of an Anthropic reply (Opus, streamed and not) and of a Z.ai reply through
# the backend llm.yaml defines, with its providerOverride: both lookups `Exact`, the Z.ai one under `zai`.
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
fake_pid=""; zai_pid=""
trap 'docker rm -f "$name" >/dev/null 2>&1; [ -n "$fake_pid" ] && kill "$fake_pid" 2>/dev/null; [ -n "$zai_pid" ] && kill "$zai_pid" 2>/dev/null; rm -rf "$tmp"' EXIT

freeport() { python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1])'; }
port="$(freeport)"; zport="$(freeport)"

cat > "$tmp/fake.py" <<'PY'
"""Stands in for api.anthropic.com (kind "anthropic": one Messages reply with cache usage, as events when
the request streams) or for api.z.ai (kind "zai": one Chat Completions reply with cached tokens)."""
import http.server
import json
import sys

PORT, OUT, KIND = int(sys.argv[1]), sys.argv[2], sys.argv[3]
ZAI_REPLY = json.dumps({
    "id": "chatcmpl_test", "object": "chat.completion", "model": "glm-5.3",
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
    "usage": {"prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010,
              "prompt_tokens_details": {"cached_tokens": 800}},
}).encode()
REPLY = json.dumps({
    "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
    "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "stop_sequence": None,
    "usage": {"input_tokens": 100, "output_tokens": 10,
              "cache_read_input_tokens": 900, "cache_creation_input_tokens": 50},
}).encode()


def event(name, data):
    return ("event: %s\ndata: %s\n\n" % (name, json.dumps(data))).encode()


# The same usage as REPLY, split as Anthropic streams it: input and cache tokens in message_start,
# the output count in message_delta.
STREAM = b"".join([
    event("message_start", {"type": "message_start", "message": {
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": [], "stop_reason": None, "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 1,
                  "cache_read_input_tokens": 900, "cache_creation_input_tokens": 50}}}),
    event("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
    event("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "ok"}}),
    event("content_block_stop", {"type": "content_block_stop", "index": 0}),
    event("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                            "usage": {"output_tokens": 10}}),
    event("message_stop", {"type": "message_stop"}),
])


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
        with open(OUT, "a") as f:
            f.write(json.dumps({"path": self.path, "body": body}) + "\n")
        if KIND == "zai":
            reply, kind = ZAI_REPLY, "application/json"
        else:
            reply, kind = (STREAM, "text/event-stream") if body.get("stream") else (REPLY, "application/json")
        self.send_response(200)
        self.send_header("content-type", kind)
        self.send_header("content-length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
PY
python3 "$tmp/fake.py" "$port" "$tmp/bodies.jsonl" anthropic & fake_pid=$!
python3 "$tmp/fake.py" "$zport" "$tmp/zai-bodies.jsonl" zai & zai_pid=$!

image="$(ROOT="$ROOT" PORT="$port" ZPORT="$zport" TMP="$tmp" OUT="$tmp/config.yaml" python3 - <<'PY'
import json
import os
import yaml

root = os.environ["ROOT"]
params = next(d for d in yaml.safe_load_all(open(f"{root}/infrastructure/base/agent-gateway/parameters.yaml"))
              if d and d["kind"] == "AgentgatewayParameters")["spec"]["image"]
backend = next(d for d in yaml.safe_load_all(open(f"{root}/infrastructure/base/agent-gateway/anthropic.yaml"))
               if d and d["kind"] == "AgentgatewayBackend")["spec"]["policies"]["ai"]
# The real manifests: the Z.ai backend's provider block (providerOverride included), aliases and routes,
# the access-log `cost` attribute, and the catalog overlay gen-prices.py renders.
zai = next(d for d in yaml.safe_load_all(open(f"{root}/infrastructure/base/agent-gateway/llm.yaml"))
           if d and d["kind"] == "AgentgatewayBackend" and d["metadata"]["name"] == "zai")["spec"]
frontend = next(d for d in yaml.safe_load_all(open(f"{root}/infrastructure/base/agent-gateway/policy-frontend.yaml"))
                if d and d["kind"] == "AgentgatewayPolicy")["spec"]["frontend"]["accessLog"]["attributes"]["add"]
cost_expr = next(a["expression"] for a in frontend if a["name"] == "cost")
overlay = next(d for d in yaml.safe_load_all(open(f"{root}/infrastructure/base/agent-gateway/model-catalog.yaml"))
               if d and d["kind"] == "ConfigMap" and d["metadata"]["name"] == "agent-model-catalog")
open(os.path.join(os.environ["TMP"], "catalog.json"), "w").write(overlay["data"]["catalog.json"])
zai_ai = zai["policies"]["ai"]
# The CRD spells a format `Completions`, the standalone config `completions`; nothing else differs.
zai_custom = {**zai["ai"]["provider"]["custom"], "formats": [
    {**f, "type": f["type"][0].lower() + f["type"][1:]} for f in zai["ai"]["provider"]["custom"]["formats"]]}
config = {
    "config": {"statsAddr": "0.0.0.0:15020", "modelCatalog": [{"file": "/catalog.json"}]},
    "frontendPolicies": {"accessLog": {"add": {"cost": cost_expr}}},
    "binds": [{"port": 3001, "listeners": [{"protocol": "HTTP", "routes": [{
        "name": "zai",
        "matches": [{"path": {"pathPrefix": "/v1"}}],
        "policies": {
            "ai": {"routes": {path: kind.lower() for path, kind in zai_ai["routes"].items()},
                   "modelAliases": zai_ai["modelAliases"]},
            "backendAuth": {"key": "test-key"},
        },
        "backends": [{"ai": {"name": "zai", "provider": {"custom": zai_custom},
                             "hostOverride": "host.docker.internal:%s" % os.environ["ZPORT"]}}],
    }]}]}, {"port": 3000, "listeners": [{"protocol": "HTTP", "routes": [{
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
  -v "$tmp/config.yaml:/config.yaml:ro" -v "$tmp/catalog.json:/catalog.json:ro" \
  -p 127.0.0.1::3000 -p 127.0.0.1::3001 -p 127.0.0.1::15020 \
  "$image" -f /config.yaml >/dev/null || { echo "cannot start $image" >&2; exit 1; }
gw="$(docker port "$name" 3000/tcp | head -1)"
zgw="$(docker port "$name" 3001/tcp | head -1)"
stats="$(docker port "$name" 15020/tcp | head -1)"

request() {  # $1: "marked", "control" or "streamed" (marked, and streamed)
  MODE="$1" python3 - <<'PY'
import json
import os

bp = {"prompt_cache_breakpoint": {"mode": "explicit"}} if os.environ["MODE"] != "control" else {}
print(json.dumps({
    "model": "agent-default", "max_tokens": 64, **({"stream": True} if os.environ["MODE"] == "streamed" else {}),
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
zai_request() {
  printf '%s' '{"model": "agent-default", "max_tokens": 64, "messages": [{"role": "user", "content": "list the files"}]}'
}
zai_request | curl -fsS --max-time 10 "http://$zgw/v1/chat/completions" -H 'content-type: application/json' -d @- >/dev/null \
  || { echo "the Z.ai request failed" >&2; docker logs "$name" 2>&1 | tail -20 >&2; exit 1; }
curl -fsS --max-time 10 "http://$stats/metrics" > "$tmp/metrics.txt" || { echo "no metrics on $stats" >&2; exit 1; }
request streamed | curl -fsS -N --max-time 10 "http://$gw/v1/chat/completions" -H 'content-type: application/json' -d @- > "$tmp/stream.txt" \
  || { echo "the streamed request failed" >&2; exit 1; }
# The gateway records a stream's usage as it ends: scrape until the output tokens have moved (the other types may land at another moment), at most 5 seconds.
for _ in $(seq 1 10); do
  curl -fsS --max-time 10 "http://$stats/metrics" > "$tmp/metrics-stream.txt" || { echo "no metrics on $stats" >&2; exit 1; }
  grep '^agentgateway_gen_ai_client_token_usage_sum{' "$tmp/metrics.txt" > "$tmp/before.txt"
  grep '^agentgateway_gen_ai_client_token_usage_sum{' "$tmp/metrics-stream.txt" > "$tmp/after.txt"
  cmp -s <(grep 'gen_ai_token_type="output"' "$tmp/before.txt") <(grep 'gen_ai_token_type="output"' "$tmp/after.txt") || break
  sleep 0.5
done

docker logs "$name" > "$tmp/gateway.log" 2>&1
BODIES="$tmp/bodies.jsonl" ZBODIES="$tmp/zai-bodies.jsonl" LOG="$tmp/gateway.log" METRICS="$tmp/metrics.txt" STREAMED="$tmp/metrics-stream.txt" ROOT="$ROOT" python3 - <<'PY'
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
# The readiness loop resends the marked request until the gateway answers: the control and the
# streamed request come last, and the first scrape counts every reply before the streamed one.
check(len(bodies) >= 3, f"the fake upstream received {len(bodies)} requests, want at least 3 (marked, control, streamed)")
marked, control, streamed = bodies[-3], bodies[-2], bodies[-1]
n = len(bodies) - 1
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

def series(path, family):
    """[(labels, value)] of one metric family in one scrape."""
    out = []
    for line in open(path):
        if line.startswith(family + "{"):
            out.append((dict(re.findall(r'(\w+)="([^"]*)"', line.split("}")[0])), float(line.rsplit(" ", 1)[1])))
    return out


def token_usage(path, provider="anthropic"):
    """{gen_ai_token_type: tokens} summed over the gateway's token series of one provider in one scrape."""
    usage = {}
    for labels, value in series(path, "agentgateway_gen_ai_client_token_usage_sum"):
        if labels.get("gen_ai_system") == provider:
            usage[labels.get("gen_ai_token_type")] = usage.get(labels.get("gen_ai_token_type"), 0) + value
    return usage


def providers(path):
    return {labels.get("gen_ai_system") for labels, _ in series(path, "agentgateway_gen_ai_client_token_usage_sum")}


check(providers(os.environ["METRICS"]) == {"anthropic", "zai"},
      f"the token series name the provider gen_ai_system, which the alerts select after the relabel: anthropic for Anthropic and zai for Z.ai (providerOverride), got {providers(os.environ['METRICS'])}")
usage = token_usage(os.environ["METRICS"])
check({"input", "output", "input_cache_read", "input_cache_write"} <= set(usage),
      f"the token types vmpodscrape.yaml relabels exist, got {sorted(usage)}")
# Each reply reports input 100, cache read 900, cache write 50: the agent-cache rules divide reads by
# input, which holds only while input counts the cached tokens too.
check(usage.get("input_cache_read") == 900 * n and usage.get("input") == 1050 * n,
      f"over {n} replies, input includes cache reads and writes ({n} x 1050) and reads are {n} x 900, as agent-cache's share assumes, got {usage}")

# Truthful costs TC4: the streamed reply is counted as the others, which the charge join and the
# meter's cost() both read as input including cache tokens.
check(streamed.get("stream") is True, f"the last request reached the upstream as a stream, got stream={streamed.get('stream')}")
after = token_usage(os.environ["STREAMED"])
delta = {t: after.get(t, 0) - usage.get(t, 0) for t in ("input", "input_cache_read", "input_cache_write", "output")}
check(delta == {"input": 1050, "input_cache_read": 900, "input_cache_write": 50, "output": 10},
      f"a streamed reply counts input 1050 (cache reads and writes included), reads 900, writes 50, output 10, got {delta}")

# Cost cross-check XC1, offline proof 2: the gateway prices each reply from the overlay catalog.
CATALOG_LOOKUPS = "agentgateway_cost_catalog_lookups_total"
COST = "agentgateway_gen_ai_client_cost_usd_total"


def cost(path, provider):
    return sum(v for labels, v in series(path, COST) if labels.get("gen_ai_system") == provider)


def lookups(path, status=None):
    """{(provider, request model, status): count} of the catalog lookups of one scrape."""
    return {(labels.get("gen_ai_system"), labels.get("gen_ai_request_model"), labels.get("status")): v
            for labels, v in series(path, CATALOG_LOOKUPS) if status in (None, labels.get("status"))}


def close(a, b):
    return abs(a - b) < 1e-9


# Opus: 100 input at 4.00, 900 cache read at 0.20, 50 cache write at 5.00, 10 output at 20.00 per million.
OPUS = 0.00103
# glm-5.3 (Z.ai): 200 uncached input at 1.40, 800 cached at 0.26, 10 output at 4.40 per million.
GLM = 0.000532
first = os.environ["METRICS"]
check(close(cost(first, "anthropic"), OPUS * n),
      f"over {n} Opus replies the gateway's cost is {n} x {OPUS} USD (the overlay's rates), got {cost(first, 'anthropic')}")
check(close(cost(first, "zai"), GLM),
      f"one Z.ai reply costs {GLM} USD under provider zai, got {cost(first, 'zai')}")
exact = lookups(first, "Exact")
check(exact.get(("anthropic", "claude-opus-5-5", "Exact")) == n and exact.get(("zai", "glm-5.3", "Exact")) == 1,
      f"the lookups are Exact: {n} for anthropic/claude-opus-5-5 and 1 for zai/glm-5.3, got {exact}")
check(not [k for k, v in lookups(first).items() if k[2] != "Exact" and v],
      f"no lookup is Missing, Unpriced or NoCatalog, got {lookups(first)}")
check(close(cost(os.environ["STREAMED"], "anthropic") - cost(first, "anthropic"), OPUS),
      f"the streamed Opus reply costs {OPUS} USD as the others, got {cost(os.environ['STREAMED'], 'anthropic') - cost(first, 'anthropic')}")
zbodies = [json.loads(line)["body"] for line in open(os.environ["ZBODIES"])]
check(len(zbodies) == 1 and zbodies[0].get("model") == "glm-5.3",
      f"the Z.ai backend's alias reaches the fake as glm-5.3, got {zbodies}")
log = open(os.environ["LOG"]).read()
# flatten(llm.cost) writes cost.total, cost.input, ... on the request's line.
check(any("gen_ai.provider.name=anthropic" in l and "cost.total=0.00103 " in l for l in log.splitlines()),
      "an access log line of an Opus reply carries cost.total=0.00103 (policy-frontend.yaml's cost attribute)")
check(any("gen_ai.provider.name=zai" in l and "cost.total=0.000532 " in l for l in log.splitlines()),
      "the access log line of the Z.ai reply names provider zai and carries cost.total=0.000532")

if fails:
    print("\n".join("FAIL  " + f for f in fails), file=sys.stderr)
    sys.exit(1)
print("PASS")
PY
