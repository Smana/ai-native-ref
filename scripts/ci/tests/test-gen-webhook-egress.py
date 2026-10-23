#!/usr/bin/env python3
# requires: python3
"""gen-webhook-egress: one egress rule per subscriber, by its network (factory interfaces F6, R21)."""
import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("gen", ROOT / "scripts/ci/gen-webhook-egress.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)

failures = []


def check(name, cond):
    if not cond:
        failures.append(name)


none = gen.render({})
check("no subscriber, an egress-only policy that allows nothing", none["spec"]["egress"] == [{}] and "ingress" not in none["spec"])

cfg = {"webhooks": [
    {"name": "slack-app", "network": "cluster", "url": "http://factory-slack-app.agent-system.svc.cluster.local:8081/webhooks"},
    {"name": "ci-mirror", "network": "internet", "url": "https://hooks.example.io/factory"},
    {"name": "own", "network": "internet", "url": "https://hooks.${public_domain_name}/factory"},
    {"name": "alt-port", "network": "internet", "url": "https://hooks.example.io:8443/factory"},
]}
rules = gen.render(cfg)["spec"]["egress"]
check("cluster: toEndpoints by namespace and name, its port",
      rules[0] == {"toEndpoints": [{"matchLabels": {"io.kubernetes.pod.namespace": "agent-system",
                                                    "app.kubernetes.io/name": "factory-slack-app"}}],
                   "toPorts": [{"ports": [{"port": "8081", "protocol": "TCP"}]}]})
check("internet: toFQDNs matchName on 443",
      rules[1] == {"toFQDNs": [{"matchName": "hooks.example.io"}], "toPorts": [{"ports": [{"port": "443", "protocol": "TCP"}]}]})
check("internet: a Flux ${var} label is kept for Flux to substitute",
      rules[2]["toFQDNs"] == [{"matchName": "hooks.${public_domain_name}"}])
check("internet: an explicit port is the rule's port",
      rules[3]["toPorts"] == [{"ports": [{"port": "8443", "protocol": "TCP"}]}])

for bad in ({"network": "internet", "url": "https://10.0.0.1/x"},
            {"network": "internet", "url": "https://[::1]/x"},
            {"network": "internet", "url": "https://localhost/x"},
            {"network": "internet", "url": "https://x.agent-system.svc.cluster.local/x"},
            {"network": "internet", "url": "https://x.svc/x"},
            {"network": "internet", "url": "https://x.corp.internal/x"},
            {"network": "internet", "url": "https://x.local/x"},
            {"network": "internet", "url": "https://hooks/x"},
            {"network": "internet", "url": "https://hooks.localdomain/x"},
            {"network": "internet", "url": "http://hooks.example.io/x"},
            {"network": "cluster", "url": "http://hooks.example.io/x"},
            {"network": "cluster", "url": "http://x.agent-system.svc.cluster.local/x"},
            {"network": "mars", "url": "https://hooks.example.io/x"}):
    try:
        gen.render({"webhooks": [dict(bad, name="x")]})
        failures.append(f"accepted {bad}")
    except gen.ConfigError:
        pass

try:
    gen.render({"webhooks": [{"name": "a", "network": "internet", "url": "https://h.example.io/x"},
                             {"name": "a", "network": "internet", "url": "https://h.example.io/y"}]})
    failures.append("accepted a duplicate name")
except gen.ConfigError:
    pass

base = {"webhooks": []}
check("an overlay with base's subscribers needs no patch", gen.overlay_patch(base, {"webhooks": []}) is None)
check("an overlay without a webhooks key needs no patch", gen.overlay_patch(base, {}) is None)
patch = gen.overlay_patch(base, cfg)
check("an overlay's own subscribers patch base's policy by name, spec replaced",
      patch["kind"] == "CiliumNetworkPolicy" and patch["metadata"]["name"] == "room-broker-webhooks"
      and patch["metadata"]["namespace"] == "agent-system"
      and patch["spec"] == gen.render(cfg)["spec"])

print("\n".join(failures) or "PASS")
sys.exit(1 if failures else 0)
