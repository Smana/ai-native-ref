#!/usr/bin/env python3
# requires: python3 kustomize
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
  M6  The planner (design L2, plan B5): base's is Z.ai glm-5.3; gcp-0's is that, or Neon on vertex
      for the test window, nothing else; the test window's patch is its own file, so reverting it
      is one line.
  M5  Gemini (design G1, G6, G7) is gcp-0's alone: its overlay adds the vertex provider (no key,
      public only), gemini-standard and gemini-light on the public listener, their meter.prices
      rows to the catalog and the two aliases to the run-controller's public list. Base and aws-0
      name none of it, and base's catalog leaves the rows out (the chart refuses a price no alias serves).

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
GEMINI = {"gemini-4-neon", "gemini-4-hydrogen"}
if values["modelCatalog"]["prices"] != {m: r for m, r in meter.items() if m not in GEMINI}:
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

# CP12: the run-controller's default light alias must be served on both listeners, or Maku refuses
# its config before any run starts. Check the values CI renders, not only the gateway's definition.
run_controller = find(docs(ROOT / "infrastructure/base/room-broker/helmrelease.yaml"),
                      "HelmRelease", "room-broker")["spec"]["values"]["runController"]
run_aliases = run_controller["model"]["gateway"]["aliases"]
for listener in BACKENDS:
    if "tier-light" not in run_aliases.get(listener, []):
        problems.append(f"CP12: runController.model.gateway.aliases.{listener} does not serve tier-light")
    if "tier-light" not in values["aliases"].get(listener, {}):
        problems.append(f"CP12: model-gateway aliases.{listener} does not serve tier-light")

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

# M5
def build(path):
    import subprocess
    out = subprocess.run(["kustomize", "build", str(ROOT / path)], capture_output=True, text=True, check=True).stdout
    return [d for d in yaml.safe_load_all(out) if isinstance(d, dict)]


def released(path, name):
    return find(build(path), "HelmRelease", name)["spec"]["values"]


gemini = {"gemini-standard": {"provider": "vertex", "model": "gemini-4-neon"},
          "gemini-light": {"provider": "vertex", "model": "gemini-4-hydrogen"}}
gcp = released("infrastructure/gcp-0/agent-gateway/model-gateway", "model-gateway")
if gcp["providers"].get("vertex") != {"preset": "vertex", "projectId": "${project_id}", "region": "eu",
                                      "dataClasses": ["public"]}:
    problems.append(f"M5: gcp-0's providers.vertex is {gcp['providers'].get('vertex')}")
if {a: t for a, t in gcp["aliases"]["public"].items() if a in gemini} != gemini \
        or any(t["provider"] == "vertex" for t in gcp["aliases"]["internal"].values()):
    problems.append("M5: gcp-0 must serve gemini-standard and gemini-light on public, and vertex on no internal alias")
if {m: r for m, r in gcp["modelCatalog"]["prices"].items() if m in GEMINI} != {m: meter[m] for m in GEMINI}:
    problems.append("M5: gcp-0's catalog does not carry meter.prices' Gemini rows")
gw = released("infrastructure/gcp-0/room-broker", "room-broker")["runController"]["model"]["gateway"]
broker = gw["aliases"]
# The harness's own counter (Maku plan A6): each Gemini alias priced at its served model's meter.prices row.
want_prices = {a: {"input": f"{meter[t['model']]['input']:.4g}", "output": f"{meter[t['model']]['output']:.4g}"}
               for a, t in gemini.items()}
if gw.get("prices") != want_prices:
    problems.append(f"M5: gcp-0's runController.model.gateway.prices {gw.get('prices')} is not meter.prices' {want_prices}")
if not set(gemini) <= set(broker["public"]) or set(gemini) & set(broker["internal"]):
    problems.append(f"M5: gcp-0's run-controller aliases {broker} must hold the Gemini aliases on public only")
# The budgets' cost map prices every meter.prices row on every cluster; the values must name none.
for path, name in (("infrastructure/aws-0/agent-gateway/model-gateway", "model-gateway"),
                   ("infrastructure/aws-0/room-broker", "room-broker"), ("infrastructure/base/room-broker", "room-broker")):
    if "gemini" in str(released(path, name)) or "vertex" in str(values):
        problems.append(f"M5: {path} or base's model gateway names Gemini; only gcp-0 reaches Vertex AI")

# M6
ZAI = {"enabled": True, "provider": "zai", "model": "glm-5.3"}
if values["clients"]["planner"] != ZAI:
    problems.append(f"M6: base's planner is {values['clients']['planner']}, not {ZAI}")
if gcp["clients"]["planner"] not in (ZAI, {"enabled": True, "provider": "vertex", "model": "gemini-4-neon"}):
    problems.append(f"M6: gcp-0's planner is {gcp['clients']['planner']}: Z.ai glm-5.3, or Neon for the test window")
kz = yaml.safe_load((ROOT / "infrastructure/gcp-0/agent-gateway/model-gateway/kustomization.yaml").read_text())
if gcp["clients"]["planner"]["provider"] == "vertex" and \
        {"path": "helmrelease-planner-gemini.yaml"} not in (kz.get("patches") or []):
    problems.append("M6: the Neon planner must come from helmrelease-planner-gemini.yaml alone, so reverting it is one line")

for p in problems:
    print(f"FAIL {p}")
print(f"==> model-gateway values: {len(problems)} problem(s)")
sys.exit(1 if problems else 0)
