#!/usr/bin/env python3
# requires: python3
"""The planner's client identity, and both halves of its one network path (CD18), on the model gateway.

The broker calls agent-gateway/model-gateway's clients listener (:8082) once per plan, on the route
/clients/planner/v1, with a projected ServiceAccount token of audience maku-gateway.client.planner
(Maku v4 step 4, ANR follow-up 3). Several things have to agree for that call to work, and each is
silent when it does not:

- The broker's values. `broker.modelGateway` names the Gateway, its namespace, the clients port and
  the audience prefix: the chart then mounts the token and opens its own NetworkPolicy to the gateway.
  The gateway's values must say the same: its name, namespace and broker subject, and a planner client.
- Every config copy. config.yaml replaces the chart's ConfigMap, so each copy's human.intake.plan must
  name the URL and token file the chart would derive. A copy still on a static key 401s every plan.
- Both CNP halves. The broker's egress names the gateway's pods on 8082; the gateway's chart policy
  admits the broker on 8082 (test-assert-agent-gateway's fixture holds that half).
- Nothing left of the Envoy AI gateway's planner path: no key ExternalSecret on either side, no
  `ai-gateway-planner-key` credential, no room-broker source in the data plane's ingress.

This reads the source tree, not the rendered bundle: all the facts are legible before a render, and
the gate stays runnable without the host profile.
"""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
GATEWAY = {"service": "model-gateway", "namespace": "agent-gateway", "port": 8082, "audiencePrefix": "maku-gateway"}
URL = "http://model-gateway.agent-gateway.svc.cluster.local:8082/clients/planner/v1"
TOKEN = "/var/run/secrets/maku/model-gateway/planner"
problems = []


def check(cond, msg):
    if not cond:
        problems.append(msg)


def docs(path):
    p = ROOT / path
    if not p.is_file():
        print(f"FAIL no such file: {path}")
        sys.exit(1)
    return [d for d in yaml.safe_load_all(p.read_text()) if d]


def load(path, name=None):
    """The first YAML document, or the one whose metadata.name is `name`."""
    found = docs(path)
    if name is not None:
        found = [d for d in found if (d.get("metadata") or {}).get("name") == name]
        if not found:
            print(f"FAIL no such document: {path} {name}")
            sys.exit(1)
    return found[0]


def ports(rule):
    return {int(p["port"]) for t in rule.get("toPorts") or [] for p in t.get("ports") or []}


# --- the broker's values and the gateway's agree ------------------------------------------------
broker = load("infrastructure/base/room-broker/helmrelease.yaml")["spec"]["values"]["broker"]
check(broker.get("modelGateway") == GATEWAY, f"broker.modelGateway is {GATEWAY}, found {broker.get('modelGateway')}")
gw_release = load("infrastructure/base/agent-gateway/model-gateway/helmrelease.yaml")
gw = gw_release["spec"]["values"]
check(gw.get("name") == GATEWAY["service"] and gw_release["metadata"]["namespace"] == GATEWAY["namespace"],
      "broker.modelGateway names the model-gateway release's Gateway and namespace")
check(gw.get("audiencePrefix", "maku-gateway") == GATEWAY["audiencePrefix"]
      and (gw.get("listeners") or {}).get("clients", 8082) == GATEWAY["port"],
      "the gateway's audience prefix and clients port are the broker's")
check((gw.get("broker") or {}).get("serviceAccount") == "room-broker"
      and (gw.get("broker") or {}).get("namespace") == "agent-system",
      "the gateway admits system:serviceaccount:agent-system:room-broker on its clients listener")
planner = (gw.get("clients") or {}).get("planner") or {}
check(planner.get("enabled") is True and planner.get("provider") == "zai" and planner.get("model") == "glm-5.3",
      "the gateway serves the planner client: Z.ai glm-5.3")

# The static key is gone: no Secret volume, no mount under /etc/room-broker/planner.
check(not [v for v in broker.get("extraVolumes") or [] if v["name"] == "planner"], "no planner Secret volume")
check(not [m for m in broker.get("extraVolumeMounts") or [] if m["name"] == "planner"], "no planner Secret mount")

# --- every config copy names the chart's derived URL and token ----------------------------------
for cloud in ("base", "aws-0", "gcp-0"):
    cfg = load(f"infrastructure/{cloud}/room-broker/config.yaml")
    plan = (((cfg.get("human") or {}).get("intake") or {}).get("plan")) or {}
    check(plan.get("url") == URL, f"{cloud}: human.intake.plan.url is {URL}, found {plan.get('url')}")
    check(plan.get("apiKeyFile") == TOKEN,
          f"{cloud}: human.intake.plan.apiKeyFile is {TOKEN}, found {plan.get('apiKeyFile')}")

# --- the broker's egress half -------------------------------------------------------------------
broker_cnp = load("infrastructure/base/room-broker/network-policy.yaml", name="room-broker")
egress = broker_cnp["spec"]["egress"]
GW_PODS = {"io.kubernetes.pod.namespace": "agent-gateway", "gateway.networking.k8s.io/gateway-name": "model-gateway"}
to_gw = [r for r in egress if any(e.get("matchLabels", {}) == GW_PODS for e in r.get("toEndpoints", []))]
check(len(to_gw) == 1 and ports(to_gw[0]) == {8082},
      "the broker's egress selects the model-gateway pods on 8082, and nothing else")
check(not [e for r in egress for e in r.get("toEndpoints", [])
           if e.get("matchLabels", {}).get("io.kubernetes.pod.namespace") == "envoy-gateway-system"],
      "no broker egress to the Envoy AI gateway's data plane")
# gcp-0's overlay patches this file by index (`/spec/egress/5` is the ZITADEL rule), so the rule goes after it.
auth = [i for i, r in enumerate(egress)
        if any(f.get("matchName") == "auth.${public_domain_name}" for f in r.get("toFQDNs") or [])]
check(len(auth) == 1 and to_gw and egress.index(to_gw[0]) > auth[0],
      "the planner's egress rule must follow the ZITADEL one (gcp-0 pins that index)")

# --- nothing of the Envoy AI gateway's planner path is left -------------------------------------
for path in ("infrastructure/base/room-broker/externalsecret-planner.yaml",
             "infrastructure/base/envoy-ai-gateway/externalsecret-planner-key.yaml"):
    check(not (ROOT / path).exists(), f"{path}: the static planner key is gone")
for path, resource in (("infrastructure/base/room-broker/kustomization.yaml", "externalsecret-planner.yaml"),
                       ("infrastructure/base/envoy-ai-gateway/kustomization.yaml", "externalsecret-planner-key.yaml")):
    check(resource not in (load(path).get("resources") or []), f"{path} no longer lists {resource}")
pol = load("infrastructure/base/envoy-ai-gateway/security-policy.yaml")
check("ai-gateway-planner-key" not in [c["name"] for c in pol["spec"]["apiKeyAuth"]["credentialRefs"]],
      "the AI gateway's API-key policy no longer carries the planner's key")
dp = load("infrastructure/base/envoy-gateway/network-policy.yaml", name="envoy-data-plane")
check(not [e for r in dp["spec"]["ingress"] for e in r.get("fromEndpoints") or []
           if e.get("matchLabels", {}).get("app.kubernetes.io/name") == "room-broker"],
      "the AI gateway's data plane no longer admits the broker")

for problem in problems:
    print(f"  FAIL {problem}")
print(f"intake plan wiring: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
