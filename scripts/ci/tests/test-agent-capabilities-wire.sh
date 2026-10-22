#!/usr/bin/env bash
# requires: docker python3 curl openssl
#
# The capability profiles' model rules on the pinned agentgateway (design P2, P4; gate items 1 and 3).
# The generator renders policy-capabilities.yaml from a copy of the profiles in which
# reviewer.internal may call tier-standard and tier-light only; the proxy image parameters.yaml pins
# then serves anthropic.yaml's backend policy and that rendering, standalone, against a fake
# Anthropic upstream that records the model it is asked for. agentgateway 1.6 has no
# llm.requestModel where a route's authorization runs, so a rule written on it refuses every call:
# a grammar gate cannot see that, a request can. Standalone proves the data plane, not the
# controller's translation of the CRDs; the live gate does.
# The identity proxy (P4) then runs from agent-runtime/identity-proxy-configmap.yaml in front of the
# same gateway, with the environment the AgentRun composition gives it: each model path carries the
# run's alias and /judge/v1 the judge's, over whatever the harness asks for.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../.." && pwd)"
if ! python3 -c 'import yaml' 2>/dev/null; then
  if [ "${CI:-}" = "true" ]; then
    echo "FAIL  no PyYAML in CI: this is the capability profiles' offline proof and must run here"; exit 1
  fi
  echo "SKIP: pyyaml not installed"; exit 77
fi
if ! docker info >/dev/null 2>&1; then
  if [ "${CI:-}" = "true" ]; then
    echo "FAIL  no docker daemon in CI: this is the capability profiles' offline proof and must run here"; exit 1
  fi
  echo "SKIP: no docker daemon"; exit 77
fi

tmp="$(mktemp -d)"
# The containers run as their images' own users and read this directory at the same path.
chmod 755 "$tmp"
gw="agent-capabilities-wire-gw-$$"
fake_pid=""
trap 'docker rm -f "$gw" >/dev/null 2>&1; [ -n "$fake_pid" ] && kill "$fake_pid" 2>/dev/null; rm -rf "$tmp"' EXIT
free_port() { python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])'; }
up_port="$(free_port)"; gw_port="$(free_port)"; gw_admin="$(free_port)"; gw_ready="$(free_port)"; gw_stats="$(free_port)"

# --- The run tokens: an RSA key, its JWKS, one token per audience, signed with openssl. ---
openssl genrsa -out "$tmp/key.pem" 2048 2>/dev/null
openssl rsa -in "$tmp/key.pem" -noout -modulus > "$tmp/modulus" 2>/dev/null
TMP="$tmp" python3 - <<'PY'
import base64, json, os, subprocess, time
tmp = os.environ["TMP"]
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
n = int(open(f"{tmp}/modulus").read().strip().split("=", 1)[1], 16)
json.dump({"keys": [{"kty": "RSA", "kid": "k1", "alg": "RS256", "use": "sig",
                     "n": b64(n.to_bytes((n.bit_length() + 7) // 8, "big")), "e": "AQAB"}]}, open(f"{tmp}/jwks.json", "w"))
for aud in ("agent-router.reviewer.internal", "agent-router.implementer.internal"):
    head = b64(json.dumps({"alg": "RS256", "kid": "k1", "typ": "JWT"}).encode())
    body = b64(json.dumps({"iss": "https://issuer.test", "aud": [aud], "exp": int(time.time()) + 3600,
                           "sub": "system:serviceaccount:agents:xplane-run-wiretest"}).encode())
    sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", f"{tmp}/key.pem"], input=f"{head}.{body}".encode(),
                         capture_output=True, check=True).stdout
    open(f"{tmp}/{aud}.jwt", "w").write(f"{head}.{body}.{b64(sig)}")
PY
chmod 644 "$tmp"/*

# --- The rendering under test: reviewer.internal narrowed to two aliases, the rest as committed. ---
mkdir -p "$tmp/root/infrastructure/base" "$tmp/root/scripts/ci"
cp -a "$ROOT/infrastructure/base/agent-gateway" "$tmp/root/infrastructure/base/"
cp "$ROOT/scripts/ci/gen-capabilities.py" "$tmp/root/scripts/ci/"
prof="$tmp/root/infrastructure/base/agent-gateway/profiles/reviewer.internal.yaml"
sed -i 's/^models: .*/models: [tier-standard, tier-light]/' "$prof"
grep -q '^models: \[tier-standard, tier-light\]$' "$prof" || { echo "cannot narrow $prof" >&2; exit 1; }
python3 "$tmp/root/scripts/ci/gen-capabilities.py" --write "$tmp/root" >/dev/null || { echo "the generator refused the test profile" >&2; exit 1; }

cat > "$tmp/fake.py" <<'PY'
"""Stands in for api.anthropic.com: records the path, the model and x-ar-model of each request."""
import http.server, json, sys
PORT, OUT = int(sys.argv[1]), sys.argv[2]
class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))))
        with open(OUT, "a") as f:
            f.write(json.dumps({"path": self.path, "model": body.get("model"), "pin": self.headers.get("x-ar-model")}) + "\n")
        reply = json.dumps({"id": "msg_test", "type": "message", "role": "assistant", "model": body.get("model"),
                            "content": [{"type": "text", "text": "ok"}], "stop_reason": "end_turn", "stop_sequence": None,
                            "usage": {"input_tokens": 10, "output_tokens": 1}}).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(reply)))
        self.end_headers()
        self.wfile.write(reply)
    def log_message(self, *args):
        pass
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
PY
python3 "$tmp/fake.py" "$up_port" "$tmp/upstream.jsonl" & fake_pid=$!

# --- The gateway: the internal listener's JWT, its model route's three rules, anthropic.yaml's backend
#     policy and the rendered capabilities-internal, as the controller would attach them. ---
image="$(ROOT="$ROOT" TMP="$tmp" PORTS="$gw_port $gw_admin $gw_ready $gw_stats $up_port" python3 - <<'PY'
import os
import yaml

root, tmp = os.environ["ROOT"], os.environ["TMP"]
port, admin, ready, stats, upstream = os.environ["PORTS"].split()
def docs(path):
    return [d for d in yaml.safe_load_all(open(path)) if d]
gw = f"{tmp}/root/infrastructure/base/agent-gateway"
params = next(d for d in docs(f"{root}/infrastructure/base/agent-gateway/parameters.yaml")
              if d["kind"] == "AgentgatewayParameters")["spec"]["image"]
anthropic = docs(f"{gw}/anthropic.yaml")
backend = next(d for d in anthropic if d["kind"] == "AgentgatewayBackend")["spec"]["policies"]["ai"]
route = next(d for d in anthropic if d["kind"] == "HTTPRoute" and d["metadata"]["name"] == "agentgateway-models-internal")
listener = next(d for d in docs(f"{gw}/policies-identity.yaml") if d["metadata"]["name"] == "listener-internal")
caps = next(d for d in docs(f"{gw}/policy-capabilities.yaml") if d["metadata"]["name"] == "capabilities-internal")
authz = {t["sectionName"]: caps["spec"]["traffic"]["authorization"]["policy"]["matchExpressions"]
         for t in caps["spec"]["targetRefs"]}
direct = {t["sectionName"]: d["spec"]["traffic"]["directResponse"] for d in anthropic
          if d["kind"] == "AgentgatewayPolicy" for t in d["spec"]["targetRefs"]}
ai = {"name": "anthropic", "provider": {"anthropic": {}}, "hostOverride": f"127.0.0.1:{upstream}",
      "policies": {"ai": {"routes": {p: k.lower() for p, k in backend["routes"].items()},
                          "modelAliases": backend["modelAliases"],
                          "transformations": {t["field"]: t["expression"] for t in backend["transformations"]}}}}
routes = []
for rule in route["spec"]["rules"]:
    match = rule["matches"][0]["path"]
    policies = {"backendAuth": {"key": "test-key"}}
    if rule["name"] in authz:
        policies["authorization"] = {"rules": [{"require": e} for e in authz[rule["name"]]]}
    if rule["name"] in direct:
        policies["directResponse"] = direct[rule["name"]]
    routes.append({"name": rule["name"],
                   "matches": [{"path": {"exact" if match["type"] == "Exact" else "pathPrefix": match["value"]}}],
                   "policies": policies, "backends": [{"ai": ai}]})
jwt = listener["spec"]["traffic"]["jwtAuthentication"]["providers"][0]
config = {
    "config": {"adminAddr": f"127.0.0.1:{admin}", "readinessAddr": f"127.0.0.1:{ready}", "statsAddr": f"127.0.0.1:{stats}"},
    "binds": [{"port": int(port), "listeners": [{"protocol": "HTTP", "policies": {"jwtAuth": {
        "mode": "strict", "providers": [{"issuer": "https://issuer.test", "audiences": jwt["audiences"],
                                         "jwks": {"file": f"{tmp}/jwks.json"}}]}},
        "routes": routes}]}],
}
yaml.safe_dump(config, open(f"{tmp}/gateway.yaml", "w"), sort_keys=False)
print("%s/%s:%s@%s" % (params["registry"], params["repository"], params["tag"], params["digest"]))
PY
)" || { echo "cannot render the gateway config" >&2; exit 1; }
chmod 644 "$tmp/gateway.yaml"
docker run -d --name "$gw" --network host -v "$tmp:$tmp:ro" "$image" -f "$tmp/gateway.yaml" >/dev/null \
  || { echo "cannot start $image" >&2; exit 1; }

fails=0
fail() { echo "FAIL  $*"; fails=$((fails + 1)); }
# call <port> <path> <aud> <body model> [x-ar-model]: prints "<status> <upstream model or ->".
call() {
  : > "$tmp/upstream.jsonl"
  local pin=()
  [ -n "${5:-}" ] && pin=(-H "x-ar-model: $5")
  local tok=()
  [ -n "$3" ] && tok=(-H "authorization: Bearer $(cat "$tmp/$3.jwt")")
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:$1$2" "${tok[@]}" "${pin[@]}" \
    -H 'content-type: application/json' -d "{\"model\": \"$4\", \"max_tokens\": 8, \"messages\": [{\"role\": \"user\", \"content\": \"hi\"}]}")"
  echo "$code $(python3 -c 'import json,sys; l=open(sys.argv[1]).read().splitlines(); print(json.loads(l[-1])["model"] if l else "-")' "$tmp/upstream.jsonl")"
}
expect() {  # expect <what> <want> <got>
  [ "$2" = "$3" ] && echo "ok    $1" || fail "$1: want '$2', got '$3'"
}

ready=""
for _ in $(seq 1 30); do
  if [ "$(docker inspect -f '{{.State.Running}}' "$gw" 2>/dev/null)" != "true" ]; then
    docker logs "$gw" 2>&1 | tail -30 >&2; echo "the gateway container exited before it answered" >&2; exit 1
  fi
  [ "$(call "$gw_port" /v1/chat/completions agent-router.reviewer.internal tier-standard | cut -d' ' -f1)" = 200 ] && { ready=1; break; }
  sleep 1
done
[ -n "$ready" ] || { docker logs "$gw" 2>&1 | tail -30 >&2; echo "the gateway never answered 200" >&2; exit 1; }

R=agent-router.reviewer.internal
echo "the gateway alone (P2, P4's gateway half)"
expect "a model the profile names reaches its alias" "200 claude-sonnet-5-5" "$(call "$gw_port" /v1/chat/completions $R tier-standard)"
expect "a model it does not name is refused 403, upstream untouched (gate 1)" "403 -" "$(call "$gw_port" /v1/chat/completions $R tier-frontier)"
expect "the Messages route holds the same rule" "403 -" "$(call "$gw_port" /anthropic/v1/messages $R tier-frontier)"
expect "x-ar-model wins over the body" "200 claude-haiku-5-5" "$(call "$gw_port" /v1/chat/completions $R tier-frontier tier-light)"
expect "a pinned model the profile does not name is refused" "403 -" "$(call "$gw_port" /v1/chat/completions $R tier-standard tier-frontier)"
expect "another role keeps its own list" "200 claude-opus-5-5" "$(call "$gw_port" /v1/chat/completions agent-router.implementer.internal tier-frontier)"
expect "an unknown name is refused before the transformation's 400" "403 -" "$(call "$gw_port" /v1/chat/completions $R gpt-9)"
# A body with no model, and an empty pin: the rule's CEL errors or finds no alias, and either must refuse.
nomodel() {  # nomodel <aud> [x-ar-model header value]: status of a body with no model
  curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:$gw_port/v1/chat/completions" \
    -H "authorization: Bearer $(cat "$tmp/$1.jwt")" -H 'content-type: application/json' "${@:2}" \
    -d '{"max_tokens": 8, "messages": [{"role": "user", "content": "hi"}]}'
}
expect "a body with no model is refused 403" "403" "$(nomodel $R)"
expect "an empty x-ar-model is refused 403" "403" "$(nomodel $R -H 'x-ar-model;')"
expect "no token is still 401" "401 -" "$(call "$gw_port" /v1/chat/completions "" tier-standard)"
models="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "http://127.0.0.1:$gw_port/v1/models" -H "authorization: Bearer $(cat "$tmp/$R.jwt")")"
expect "/v1/models keeps its 404: the rule does not target it" "404" "$models"
gwlog="$(docker logs "$gw" 2>&1)"
grep 'http.status=403' <<<"$gwlog" | grep -q 'jwt.sub=system:serviceaccount:agents:xplane-run-wiretest' \
  && echo "ok    a refusal's access log names the run (gate 1)" || fail "no 403 access log line names jwt.sub"

# --- P4's sidecar half: the identity proxy from the real ConfigMap, holding the reviewer's token, in front
#     of the same gateway. Its image is the one crossplane-configuration's AgentRun composition pins. ---
ENVOY_IMAGE="docker.io/envoyproxy/envoy:distroless-v1.39.1@sha256:eb2c01c13125d1629637cb4e4cce7207009fb7cc2c8027f9742758549d15b6f4"
px="agent-capabilities-wire-px-$$"
trap 'docker rm -f "$gw" "$px" >/dev/null 2>&1; [ -n "$fake_pid" ] && kill "$fake_pid" 2>/dev/null; rm -rf "$tmp"' EXIT
px_port="$(free_port)"; px_health="$(free_port)"
mkdir -p "$tmp/token" && cp "$tmp/$R.jwt" "$tmp/token/token" && chmod 755 "$tmp/token" && chmod 644 "$tmp/token/token"
ROOT="$ROOT" TMP="$tmp" PORTS="$px_port $px_health $gw_port" python3 - <<'PY' || { echo "cannot render the proxy config" >&2; exit 1; }
import os
import yaml

root, tmp = os.environ["ROOT"], os.environ["TMP"]
port, health, gateway = (int(p) for p in os.environ["PORTS"].split())
data = next(d for d in yaml.safe_load_all(open(f"{root}/infrastructure/base/agent-runtime/identity-proxy-configmap.yaml"))
            if d and d["kind"] == "ConfigMap")["data"]
open(f"{tmp}/sds-gateway.yaml", "w").write(data["sds-gateway.yaml"].replace("/var/run/secrets/agents/gateway", f"{tmp}/token"))
cfg = yaml.safe_load(data["envoy.yaml"].replace("/etc/envoy/sds-gateway.yaml", f"{tmp}/sds-gateway.yaml")
                     .replace("/var/run/secrets/agents/gateway", f"{tmp}/token"))
# The admin socket's path is the pod's; admin is not under test.
cfg["admin"] = {"address": {"socket_address": {"address": "127.0.0.1", "port_value": 0}}}
lst = {l["name"]: l for l in cfg["static_resources"]["listeners"]}
lst["internal"]["address"]["socket_address"]["port_value"] = port
lst["health"]["address"]["socket_address"].update(address="127.0.0.1", port_value=health)
cfg["static_resources"]["listeners"] = [lst["internal"], lst["health"]]
cluster = next(c for c in cfg["static_resources"]["clusters"] if c["name"] == "agent_router_internal")
cluster["type"] = "STATIC"
cluster["load_assignment"]["endpoints"][0]["lb_endpoints"][0]["endpoint"]["address"]["socket_address"].update(
    address="127.0.0.1", port_value=gateway)
cfg["static_resources"]["clusters"] = [cluster]
yaml.safe_dump(cfg, open(f"{tmp}/envoy.yaml", "w"), sort_keys=False)
PY
chmod 644 "$tmp/envoy.yaml" "$tmp/sds-gateway.yaml"
proxy() {  # proxy [NAME=VALUE ...]: (re)starts the identity proxy with that environment
  docker rm -f "$px" >/dev/null 2>&1
  local envs=()
  for e in "$@"; do envs+=(-e "$e"); done
  docker run -d --name "$px" --network host "${envs[@]}" -v "$tmp:$tmp:ro" "$ENVOY_IMAGE" \
    -c "$tmp/envoy.yaml" --log-level warn --disable-hot-restart --concurrency 1 >/dev/null || { echo "cannot start $ENVOY_IMAGE" >&2; exit 1; }
  for _ in $(seq 1 30); do
    curl -fs -o /dev/null --max-time 2 "http://127.0.0.1:$px_health/ready" && return 0
    sleep 0.5
  done
  docker logs "$px" 2>&1 | tail -20 >&2; echo "the identity proxy never became ready" >&2; exit 1
}
# The harness's view: no token (the proxy adds it), and it asks for tier-frontier in the body and the header.
via() { call "$px_port" "$1" "" tier-frontier tier-frontier; }
upstream_path() { python3 -c 'import json,sys; l=open(sys.argv[1]).read().splitlines(); print(json.loads(l[-1])["path"] if l else "-")' "$tmp/upstream.jsonl"; }

echo "through the identity proxy (P4's sidecar half, gate 3)"
proxy MODEL=tier-standard JUDGE_MODEL=tier-light
expect "/v1 reaches the run's model, whatever the body and the harness's header say" "200 claude-sonnet-5-5" "$(via /v1/chat/completions)"
expect "/anthropic is pinned too" "200 claude-sonnet-5-5" "$(via /anthropic/v1/messages)"
expect "/judge/v1 reaches the judge's model" "200 claude-haiku-5-5" "$(via /judge/v1/chat/completions)"
expect "on the gateway's /v1" "/v1/chat/completions" "$(upstream_path)"
proxy MODEL=tier-standard JUDGE_MODEL=none
expect "no judge on the claim: /judge/v1 is refused" "403 -" "$(via /judge/v1/chat/completions)"
expect "and /v1 still answers" "200 claude-sonnet-5-5" "$(via /v1/chat/completions)"
proxy MODEL=tier-frontier JUDGE_MODEL=none
expect "a run created with a model its profile refuses fails at its first call" "403 -" "$(via /v1/chat/completions)"
proxy
expect "a proxy without MODEL (a ConfigMap ahead of the composition) refuses: the composition ships first" "403 -" "$(via /v1/chat/completions)"

[ "$fails" -eq 0 ] || { echo "$fails failure(s)"; exit 1; }
echo PASS
