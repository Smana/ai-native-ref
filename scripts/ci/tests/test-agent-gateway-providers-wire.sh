#!/usr/bin/env bash
# requires: docker python3 curl
#
# The selectable providers across the pinned agentgateway (feature 15). The proxy image
# parameters.yaml pins runs standalone with the real manifests' pieces: the three backends' provider
# blocks, aliases, typed routes and `model` transformations (llm.yaml, moonshot.yaml, mistral.yaml),
# their header-matched routing (llm.yaml's `moonshot` and `mistral` rules, Gateway API ranks a header
# match above the bare /v1 rule), and the catalog overlay gen-prices.py renders. Fake Z.ai, Kimi Code
# and Mistral upstreams answer a Chat Completions reply with cached tokens. It checks:
#   - x-ar-model: kimi-frontier reaches the Kimi fake as model k3.1-pro, the Kimi path and key;
#   - mistral-standard and mistral-light reach the Mistral fake with their dated ids;
#   - a control on today's tier-light still reaches the Z.ai fake, as glm-5.3-flash;
#   - a body that names kimi-frontier with no pin is refused 400 and reaches no upstream;
#   - each reply's prompt_tokens_details.cached_tokens is counted as input_cache_read, and the cost
#     lookup is `Exact` under moonshot and mistral, at the cost the overlay's rates give.
# Standalone proves the proxy's behaviour, not the controller's translation of the CRDs (proven live).
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
python3 -c 'import yaml' 2>/dev/null || { echo "SKIP: pyyaml not installed"; exit 77; }
if ! docker info >/dev/null 2>&1; then
  if [ "${CI:-}" = "true" ]; then
    echo "FAIL  no docker daemon in CI: the providers wire test must run here"; exit 1
  fi
  echo "SKIP: no docker daemon"; exit 77
fi

tmp="$(mktemp -d)"
name="agent-gateway-providers-wire-$$"
pids=""
trap 'docker rm -f "$name" >/dev/null 2>&1; for p in $pids; do kill "$p" 2>/dev/null; done; rm -rf "$tmp"' EXIT

freeport() { python3 -c 'import socket; s=socket.socket(); s.bind(("", 0)); print(s.getsockname()[1])'; }
zport="$(freeport)"; kport="$(freeport)"; mport="$(freeport)"

cat > "$tmp/fake.py" <<'PY'
"""Stands in for one provider: logs each request (path, authorization, body) and answers one Chat
Completions reply with cached tokens, where Kimi Code reports them in both fields (the probe)."""
import http.server
import json
import sys

PORT, OUT, KIND = int(sys.argv[1]), sys.argv[2], sys.argv[3]
USAGE = {"prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010,
         "prompt_tokens_details": {"cached_tokens": 800}}
if KIND == "moonshot":
    USAGE["cached_tokens"] = 800
REPLY = json.dumps({
    "id": "chatcmpl_test", "object": "chat.completion", "model": KIND,
    "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok",
                                         **({"reasoning_content": "thinking"} if KIND == "moonshot" else {})},
                 "finish_reason": "stop"}],
    "usage": USAGE,
}).encode()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
        with open(OUT, "a") as f:
            f.write(json.dumps({"path": self.path, "auth": self.headers.get("authorization"), "body": body}) + "\n")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(REPLY)))
        self.end_headers()
        self.wfile.write(REPLY)

    def log_message(self, *args):
        pass


http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
PY
for spec in "$zport zai" "$kport moonshot" "$mport mistral"; do
  set -- $spec
  python3 "$tmp/fake.py" "$1" "$tmp/$2.jsonl" "$2" & pids="$pids $!"
done

image="$(ROOT="$ROOT" ZPORT="$zport" KPORT="$kport" MPORT="$mport" TMP="$tmp" OUT="$tmp/config.yaml" python3 - <<'PY'
import os
import yaml

root = os.environ["ROOT"]
gw = f"{root}/infrastructure/base/agent-gateway"
params = next(d for d in yaml.safe_load_all(open(f"{gw}/parameters.yaml"))
              if d and d["kind"] == "AgentgatewayParameters")["spec"]["image"]


def backend(file, name):
    return next(d for d in yaml.safe_load_all(open(f"{gw}/{file}"))
                if d and d["kind"] == "AgentgatewayBackend" and d["metadata"]["name"] == name)["spec"]


def route_of(file, rule):
    return next(r for d in yaml.safe_load_all(open(f"{gw}/{file}")) if d and d["kind"] == "HTTPRoute"
                for r in d["spec"]["rules"] if r["name"] == rule)


frontend = next(d for d in yaml.safe_load_all(open(f"{gw}/policy-frontend.yaml"))
                if d and d["kind"] == "AgentgatewayPolicy")["spec"]["frontend"]["accessLog"]["attributes"]["add"]
cost_expr = next(a["expression"] for a in frontend if a["name"] == "cost")
overlay = next(d for d in yaml.safe_load_all(open(f"{gw}/model-catalog.yaml")) if d and d["kind"] == "ConfigMap")
open(os.path.join(os.environ["TMP"], "catalog.json"), "w").write(overlay["data"]["catalog.json"])


def lower(s):
    return s[0].lower() + s[1:]


def route(rule_name, file, backend_name, port):
    spec = backend(file, backend_name)
    ai = spec["policies"]["ai"]
    custom = {**spec["ai"]["provider"]["custom"],
              "formats": [{**f, "type": lower(f["type"])} for f in spec["ai"]["provider"]["custom"]["formats"]]}
    rule = route_of("llm.yaml", rule_name) if rule_name != "openai" else route_of("llm.yaml", "openai")
    matches = []
    for m in rule["matches"]:
        item = {"path": {"pathPrefix": m["path"]["value"]}}
        if m.get("headers"):
            item["headers"] = [{"name": h["name"], "value": {"exact": h["value"]}} for h in m["headers"]]
        matches.append(item)
    policies = {
        "ai": {"routes": {path: kind.lower() for path, kind in ai["routes"].items()},
               "modelAliases": ai["modelAliases"],
               **({"transformations": {t["field"]: t["expression"] for t in ai["transformations"]}}
                  if ai.get("transformations") else {})},
        "backendAuth": {"key": f"key-{backend_name}"},
    }
    return {"name": rule_name, "matches": matches, "policies": policies,
            "backends": [{"ai": {"name": backend_name, "provider": {"custom": custom},
                                 "hostOverride": "host.docker.internal:%s" % port}}]}


config = {
    "config": {"statsAddr": "0.0.0.0:15020", "modelCatalog": [{"file": "/catalog.json"}]},
    "frontendPolicies": {"accessLog": {"add": {"cost": cost_expr}}},
    "binds": [{"port": 3000, "listeners": [{"protocol": "HTTP", "routes": [
        route("moonshot", "moonshot.yaml", "moonshot", os.environ["KPORT"]),
        route("mistral", "mistral.yaml", "mistral", os.environ["MPORT"]),
        route("openai", "llm.yaml", "zai", os.environ["ZPORT"]),
    ]}]}],
}
yaml.safe_dump(config, open(os.environ["OUT"], "w"), sort_keys=False)
print("%s/%s:%s@%s" % (params["registry"], params["repository"], params["tag"], params["digest"]))
PY
)" || { echo "cannot render the gateway config" >&2; exit 1; }

docker run -d --name "$name" --add-host=host.docker.internal:host-gateway \
  -v "$tmp/config.yaml:/config.yaml:ro" -v "$tmp/catalog.json:/catalog.json:ro" \
  -p 127.0.0.1::3000 -p 127.0.0.1::15020 \
  "$image" -f /config.yaml >/dev/null || { echo "cannot start $image" >&2; exit 1; }
gw="$(docker port "$name" 3000/tcp | head -1)"
stats="$(docker port "$name" 15020/tcp | head -1)"

call() {  # $1: x-ar-model pin or "none", $2: the body's model
  local args=(-sS --max-time 10 -o "$tmp/last.json" -w '%{http_code}' "http://$gw/v1/chat/completions" -H 'content-type: application/json')
  [ "$1" = "none" ] || args+=(-H "x-ar-model: $1")
  printf '{"model": "%s", "max_tokens": 64, "messages": [{"role": "user", "content": "hi"}]}' "$2" | curl "${args[@]}" -d @- 2>>"$tmp/curl.err"
}

ready=""; code=""
for _ in $(seq 1 30); do
  if [ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null)" != "true" ]; then
    docker logs "$name" 2>&1 | tail -30 >&2; echo "the gateway container exited before it answered" >&2; exit 1
  fi
  code="$(call tier-light tier-light)"
  if [ "$code" = "200" ]; then ready=1; break; fi
  sleep 1
done
[ -n "$ready" ] || { docker logs "$name" 2>&1 | tail -30 >&2; echo "the gateway never answered: last status ${code:-none}, curl: $(cat "$tmp/curl.err")" >&2; exit 1; }
# The readiness loop may have sent the control more than once: counts below are of what follows.
: > "$tmp/zai.jsonl"
control_code="$(call tier-light tier-light)"
kimi_code="$(call kimi-frontier kimi-frontier)"
std_code="$(call mistral-standard mistral-standard)"
light_code="$(call mistral-light mistral-light)"
# The pin wins over the body's name, as the identity proxy's P4 sets it.
pin_code="$(call kimi-frontier agent-default)"
body_code="$(call none kimi-frontier)"
sleep 1
curl -fsS --max-time 10 "http://$stats/metrics" > "$tmp/metrics.txt" || { echo "no metrics on $stats" >&2; exit 1; }
docker logs "$name" > "$tmp/gateway.log" 2>&1

CODES="$control_code $kimi_code $std_code $light_code $pin_code $body_code" DIR="$tmp" METRICS="$tmp/metrics.txt" LOG="$tmp/gateway.log" python3 - <<'PY'
import json
import os
import re
import sys

fails = []
def check(ok, message):
    if not ok:
        fails.append(message)

control, kimi, std, light, pin, body = os.environ["CODES"].split()
d = os.environ["DIR"]


def read(name):
    try:
        return [json.loads(line) for line in open(f"{d}/{name}.jsonl")]
    except FileNotFoundError:
        return []


zai, moon, mist = read("zai"), read("moonshot"), read("mistral")
check([control, kimi, std, light, pin] == ["200"] * 5, f"the five routed calls answer 200, got {control} {kimi} {std} {light} {pin}")
check(body == "400", f"a body-only kimi-frontier with no pin is refused 400 (the model transformation nulls it), got {body}")
check(len(zai) == 1 and zai[0]["body"].get("model") == "glm-5.3-flash" and zai[0]["auth"] == "Bearer key-zai",
      f"the control on tier-light reaches Z.ai once as glm-5.3-flash, got {zai}")
check(len(moon) == 2 and all(r["body"].get("model") == "k3.1-pro" for r in moon)
      and all(r["path"] == "/coding/v1/chat/completions" and r["auth"] == "Bearer key-moonshot" for r in moon),
      f"the pinned kimi-frontier calls (one named, one pinned over agent-default) reach Kimi Code as k3.1-pro on its path and key, got {moon}")
check([r["body"].get("model") for r in mist] == ["mistral-medium-2604", "mistral-small-2603"]
      and all(r["path"] == "/v1/chat/completions" and r["auth"] == "Bearer key-mistral" for r in mist),
      f"mistral-standard then mistral-light reach Mistral as their dated ids, got {mist}")
check(not any(r["body"].get("model") == "kimi-frontier" for r in zai + moon + mist),
      "no upstream received the name kimi-frontier from the unpinned body")


def series(path, family):
    out = []
    for line in open(path):
        if line.startswith(family + "{"):
            out.append((dict(re.findall(r'(\w+)="([^"]*)"', line.split("}")[0])), float(line.rsplit(" ", 1)[1])))
    return out


def usage(provider):
    u = {}
    for labels, v in series(os.environ["METRICS"], "agentgateway_gen_ai_client_token_usage_sum"):
        if labels.get("gen_ai_system") == provider:
            u[labels["gen_ai_token_type"]] = u.get(labels["gen_ai_token_type"], 0) + v
    return u


# Each reply: 1000 prompt tokens of which 800 cached, 10 completion.
for provider, n in (("moonshot", 2), ("mistral", 2)):
    u = usage(provider)
    check(u.get("input") == 1000 * n and u.get("input_cache_read") == 800 * n and u.get("output") == 10 * n,
          f"{provider}: {n} replies count input 1000 each with 800 cache reads, got {u}")
lookups = {(l.get("gen_ai_system"), l.get("gen_ai_request_model"), l.get("status")): v
           for l, v in series(os.environ["METRICS"], "agentgateway_cost_catalog_lookups_total")}
for key in (("moonshot", "k3.1-pro", "Exact"), ("mistral", "mistral-medium-2604", "Exact"),
            ("mistral", "mistral-small-2603", "Exact")):
    check(lookups.get(key, 0) >= 1, f"the cost lookup is Exact for {key}, got {lookups}")
check(not [k for k, v in lookups.items() if k[2] != "Exact" and v], f"no lookup is Missing or Unpriced, got {lookups}")


def cost(provider):
    return sum(v for l, v in series(os.environ["METRICS"], "agentgateway_gen_ai_client_cost_usd_total")
               if l.get("gen_ai_system") == provider)


# 200 uncached input and 800 cached, 10 output, per reply. k3.1-pro: 2.00 / 0.20 / 10.00 per million.
KIMI = (200 * 2.00 + 800 * 0.20 + 10 * 10.00) / 1e6
# medium 1.50 / 0.15 / 7.50, small 0.15 / 0.015 / 0.60.
MISTRAL = (200 * 1.50 + 800 * 0.15 + 10 * 7.50 + 200 * 0.15 + 800 * 0.015 + 10 * 0.60) / 1e6
check(abs(cost("moonshot") - 2 * KIMI) < 1e-9, f"two Kimi replies cost {2 * KIMI}, got {cost('moonshot')}")
check(abs(cost("mistral") - MISTRAL) < 1e-9, f"the two Mistral replies cost {MISTRAL}, got {cost('mistral')}")

if fails:
    print("\n".join("FAIL  " + f for f in fails), file=sys.stderr)
    sys.exit(1)
print("PASS")
PY
rc=$?
[ "$rc" -eq 0 ] || { echo "--- gateway log" >&2; tail -20 "$tmp/gateway.log" >&2; }
exit "$rc"
