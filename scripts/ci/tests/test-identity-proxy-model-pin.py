#!/usr/bin/env python3
# requires: python3
"""Every route of the identity proxy that reaches the agent router's model routes pins the model.

Capability profiles design, P4: the proxy sets x-ar-model on every path the gateway serves a model
on, over any value the harness sends, so a run calls the alias it was created with: from MODEL on
/v1/ and /anthropic/, from JUDGE_MODEL on /judge/v1/, which it rewrites to /v1/. A new prefix to the
router without the header would be a way around the pin, and the wire test only probes the three it
knows; this reads them all. /mcp and /github/ carry no model. The real tree."""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
CONFIGMAP = ROOT / "infrastructure/base/agent-runtime/identity-proxy-configmap.yaml"
NO_MODEL = ("/mcp", "/github/")
WANT = {"/v1/": ("MODEL", None), "/anthropic/": ("MODEL", None), "/judge/v1/": ("JUDGE_MODEL", "/v1/")}

fails = []
cm = next(d for d in yaml.safe_load_all(CONFIGMAP.read_text()) if d and d.get("kind") == "ConfigMap")
envoy = yaml.safe_load(cm["data"]["envoy.yaml"])
for listener in envoy["static_resources"]["listeners"]:
    for chain in listener.get("filter_chains") or []:
        for f in chain.get("filters") or []:
            for vhost in ((f.get("typed_config") or {}).get("route_config") or {}).get("virtual_hosts") or []:
                prefixes = set()
                for r in vhost.get("routes") or []:
                    prefix = (r.get("match") or {}).get("prefix")
                    cluster = (r.get("route") or {}).get("cluster", "")
                    if not cluster.startswith("agent_router_") or cluster == "agent_router_sts" or prefix in NO_MODEL:
                        continue
                    prefixes.add(prefix)
                    want = WANT.get(prefix)
                    pins = [h for h in r.get("request_headers_to_add") or [] if (h.get("header") or {}).get("key") == "x-ar-model"]
                    where = f"{listener['name']} {prefix}"
                    if want is None:
                        fails.append(f"{where}: a route to {cluster} that is neither a model path nor /mcp or /github/")
                        continue
                    if len(pins) != 1 or pins[0]["header"].get("value") != f"%ENVIRONMENT({want[0]})%" \
                            or pins[0].get("append_action") != "OVERWRITE_IF_EXISTS_OR_ADD":
                        fails.append(f"{where}: must set x-ar-model to %ENVIRONMENT({want[0]})% with "
                                     f"OVERWRITE_IF_EXISTS_OR_ADD, got {pins}")
                    if (r.get("route") or {}).get("prefix_rewrite") != want[1]:
                        fails.append(f"{where}: prefix_rewrite must be {want[1]}, got {(r.get('route') or {}).get('prefix_rewrite')}")
                if prefixes and prefixes != set(WANT):
                    fails.append(f"{listener['name']}: model paths {sorted(prefixes)}, expected {sorted(WANT)}")

for fail in fails:
    print("FAIL", fail)
if fails:
    sys.exit(1)
print("PASS: every model path of the identity proxy pins x-ar-model")
