#!/usr/bin/env python3
# requires: python3
"""The model gateway's values (infrastructure/base/agent-gateway/model-gateway) serve what agent-router serves.

Until follow-up 5 deletes agent-router's model files, the two Gateways hold the same facts twice, so
this ties the copies:

  M1  modelCatalog.prices carries meter.prices' rates (the Factory's spec.prices), row for row.
  M2  Each listener's aliases map to the models agent-router's backends map them to: public is the
      Z.ai, Kimi Code and Mistral backends' modelAliases, internal the Anthropic backend's.
  M3  Each provider reads the Secret agent-router's backend reads, and provider-keys.yaml copies that
      Secret, by the same name and key, from agent-system.
  M4  The budgets overlay charges agent-router's server, domain and cost, so a run, the fleet and
      Anthropic each keep one bucket across both Gateways.

Run: python3 scripts/ci/tests/test-model-gateway-values.py
"""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
AGR = ROOT / "infrastructure/base/agent-gateway"
MGW = ROOT / "infrastructure/base/agent-gateway/model-gateway"
RATES = ("input", "cacheRead", "cacheWrite", "output")
# agent-router's model backends by listener (ADR-0054), and the chart provider each one becomes.
BACKENDS = {"public": {"zai": "zai", "moonshot": "moonshot", "mistral": "mistral"},
            "internal": {"anthropic": "anthropic"}}


def docs(path):
    return [d for d in yaml.safe_load_all(path.read_text()) if isinstance(d, dict)]


def find(objs, kind, name, namespace=None):
    hits = [o for o in objs if o.get("kind") == kind and o["metadata"]["name"] == name
            and (namespace is None or o["metadata"].get("namespace") == namespace)]
    assert len(hits) == 1, f"{kind} {namespace or '*'}/{name}: found {len(hits)}"
    return hits[0]


router = [d for f in sorted(AGR.glob("*.yaml")) for d in docs(f)]
values = find(docs(MGW / "helmrelease.yaml"), "HelmRelease", "model-gateway")["spec"]["values"]
problems = []

# M1
factory = find(docs(ROOT / "tooling/base/agent-factory/resources/factory.yaml"), "Factory", "${cluster_name}")
meter = {m: {f: r[f] for f in RATES if f in r} for m, r in factory["spec"]["prices"].items()}
if values["modelCatalog"]["prices"] != meter:
    problems.append(f"M1: modelCatalog.prices {values['modelCatalog']['prices']} is not meter.prices' rates {meter}")

# M2, M3
keys = {d["metadata"]["name"]: d for d in docs(MGW / "provider-keys.yaml") if d.get("kind") == "ExternalSecret"}
for listener, backends in BACKENDS.items():
    want = {}
    for backend, provider in backends.items():
        b = find(router, "AgentgatewayBackend", backend, "agent-system")["spec"]
        want.update({alias: {"provider": provider, "model": model}
                     for alias, model in b["policies"]["ai"]["modelAliases"].items()})
        secret = b["policies"]["auth"]["secretRef"]
        p = values["providers"][provider]
        if (p["existingSecret"], p.get("key", "apiKey")) != (secret["name"], secret["key"]):
            problems.append(f"M3: providers.{provider} reads {p['existingSecret']}/{p.get('key', 'apiKey')}, "
                            f"agent-router's {backend} {secret['name']}/{secret['key']}")
        copy = keys.get(p["existingSecret"])
        data = (copy or {}).get("spec", {}).get("data") or [{}]
        if not copy or copy["spec"]["secretStoreRef"]["name"] != "agent-system-provider-keys" or data != [
                {"secretKey": secret["key"], "remoteRef": {"key": secret["name"], "property": secret["key"]}}]:
            problems.append(f"M3: provider-keys.yaml does not copy agent-system/{secret['name']} key {secret['key']}")
        if listener not in p.get("dataClasses", ["public"]):
            problems.append(f"M2: providers.{provider}.dataClasses {p.get('dataClasses')} leave out {listener}")
    if values["aliases"][listener] != want:
        problems.append(f"M2: aliases.{listener} {values['aliases'][listener]} is not agent-router's {want}")

# M4
ours = find(docs(MGW / "policy-budgets.yaml"), "AgentgatewayPolicy", "model-gateway-token-budgets")
theirs = find(router, "AgentgatewayPolicy", "token-budgets", "agent-gateway")
o, t = ours["spec"]["traffic"]["rateLimit"], theirs["spec"]["traffic"]["rateLimit"]
for field in ("backendRef", "domain", "failureMode"):
    if o["global"].get(field) != t["global"].get(field):
        problems.append(f"M4: rateLimit.global.{field} {o['global'].get(field)!r} is not agent-router's {t['global'].get(field)!r}")
if [d["cost"] for d in o["global"]["descriptors"]] != [d["cost"] for d in t["global"]["descriptors"]]:
    problems.append("M4: a descriptor's cost differs from agent-router's (gate AG8 regenerates it from meter.prices)")
if [[e["name"] for e in d["entries"]] for d in o["global"]["descriptors"]] != \
        [[e["name"] for e in d["entries"]] for d in t["global"]["descriptors"]]:
    problems.append("M4: the descriptors are not agent-router's B1, B2 and B6, in order")
if o.get("local") != t.get("local"):
    problems.append(f"M4: the local backstop {o.get('local')} is not agent-router's {t.get('local')}")
if ours["spec"]["targetRefs"] != [{"group": "gateway.networking.k8s.io", "kind": "Gateway", "name": values["name"]}]:
    problems.append(f"M4: the budgets target {ours['spec']['targetRefs']}, not Gateway {values['name']}")

for p in problems:
    print(f"FAIL {p}")
print(f"==> model-gateway values: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
