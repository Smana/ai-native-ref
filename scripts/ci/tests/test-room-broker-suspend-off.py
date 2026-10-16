#!/usr/bin/env python3
# requires: python3
"""v2 warm-sandboxes S5: the room broker's suspend trigger stays off until the owner turns it
on. Its one grant, patch on agentruns, lives only in room-broker/suspend, whose Flux
Kustomization no cluster lists; the broker's own RBAC never patches or updates a run; its
config never enables suspend; and the Kyverno limit that fences the grant is always there,
for the broker alone, naming exactly the three suspend annotations."""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
BROKER = "system:serviceaccount:agent-system:room-broker"
ANNOTATIONS = ["agents.ogenki.io/operating-mode", "agents.ogenki.io/remaining-seconds",
               "agents.ogenki.io/resumed-at"]


def docs(path):
    return [d for d in yaml.safe_load_all((ROOT / path).read_text()) if d]


def run_rules(path):
    return [(r, d) for d in docs(path) if d["kind"] == "Role" for r in d["rules"]
            if "agentruns" in r.get("resources", [])]


checks = {}
for cluster in sorted((ROOT / "clusters").glob("*-agent-platform")):
    listed = yaml.safe_load((cluster / "kustomization.yaml").read_text())["resources"]
    ks = cluster / "infrastructure-room-broker-suspend.yaml"
    checks[f"{cluster.name}: the suspend Kustomization exists"] = ks.is_file()
    checks[f"{cluster.name}: and is not listed"] = ks.name not in listed
    if ks.is_file():
        spec = docs(ks.relative_to(ROOT))[0]["spec"]
        checks[f"{cluster.name}: it applies room-broker-suspend"] = \
            spec["path"] == "./infrastructure/base/room-broker/suspend"

checks["the broker's own RBAC never patches or updates a run"] = all(
    not {"patch", "update"} & set(r["verbs"]) for r, _ in run_rules("infrastructure/base/room-broker/rbac.yaml"))

grant = run_rules("infrastructure/base/room-broker/suspend/rbac.yaml")
bindings = [d for d in docs("infrastructure/base/room-broker/suspend/rbac.yaml") if d["kind"] == "RoleBinding"]
checks["the grant is patch on agentruns in agents, nothing else"] = (
    len(grant) == 1 and grant[0][0]["verbs"] == ["patch"] and grant[0][0]["resources"] == ["agentruns"]
    and grant[0][1]["metadata"]["namespace"] == "agents"
    and len(docs("infrastructure/base/room-broker/suspend/rbac.yaml")) == 2)
checks["it is bound to the broker's ServiceAccount alone"] = (
    len(bindings) == 1 and bindings[0]["subjects"] == [
        {"kind": "ServiceAccount", "name": "room-broker", "namespace": "agent-system"}])

config = yaml.safe_load((ROOT / "infrastructure/base/room-broker/config.yaml").read_text())
checks["the broker's config never enables suspend"] = not (config.get("suspend") or {}).get("enabled", False)

limit = [d for d in docs("security/base/agent-policies/validatingpolicies.yaml")
         if d["metadata"]["name"] == "agentrun-broker-patch-limit"]
checks["the broker's patch limit exists"] = len(limit) == 1
if limit:
    spec = limit[0]["spec"]
    variables = {v["name"]: v["expression"] for v in spec["variables"]}
    rules = spec["matchConstraints"]["resourceRules"]
    checks["it denies, failing closed"] = spec["validationActions"] == ["Deny"] and spec["failurePolicy"] == "Fail"
    checks["it matches the broker's AgentRun updates"] = (
        BROKER in spec["matchConditions"][0]["expression"]
        and rules == [{"apiGroups": ["cloud.ogenki.io"], "apiVersions": ["v1alpha1"], "operations": ["UPDATE"],
                       "resources": ["agentruns"]}])
    checks["it allows exactly the three suspend annotations"] = (
        [variables[k].strip("'") for k in ("mode", "left", "resumed")] == ANNOTATIONS
        and variables["allowed"] == "[variables.mode, variables.left, variables.resumed]")
    checks["it requires a suspendable run"] = any(
        "object.spec.suspendable == true" in v["expression"] for v in spec["validations"])

fails = 0
for desc, ok in checks.items():
    print(f"  {'ok  ' if ok else 'FAIL'} {desc}")
    fails += not ok
sys.exit(1 if fails else 0)
