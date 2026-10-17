#!/usr/bin/env python3
# requires: python3 kustomize
"""v2 warm-sandboxes S5: the room broker's suspend trigger is on exactly where the three
switches agree, gcp-0 today, and off everywhere else. A cluster in ON lists the
room-broker-suspend Kustomization, renders the broker's suspend.enabled with after 5m, and
renders the factory's sandbox.suspend.enabled; any other cluster has none of the three, so a
half-on cluster (a grant with no trigger, or suspendable runs nobody suspends) fails here.
The grant, patch on agentruns, lives only in room-broker/suspend; the broker's own RBAC
never patches or updates a run; base's config never enables suspend, and gcp-0's copy of it
differs in suspend alone; and the Kyverno limit that fences the grant is always there, for
the broker alone, naming exactly the three suspend annotations."""
import pathlib
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
BROKER = "system:serviceaccount:agent-system:room-broker"
ON = {"gcp-0"}
ANNOTATIONS = ["agents.ogenki.io/operating-mode", "agents.ogenki.io/remaining-seconds",
               "agents.ogenki.io/resumed-at"]


def docs(path):
    return [d for d in yaml.safe_load_all((ROOT / path).read_text()) if d]


def run_rules(path):
    return [(r, d) for d in docs(path) if d["kind"] == "Role" for r in d["rules"]
            if "agentruns" in r.get("resources", [])]


def build(path):
    out = subprocess.run(["kustomize", "build", str(ROOT / path)], capture_output=True, text=True, check=True)
    return [d for d in yaml.safe_load_all(out.stdout) if d]


def broker_suspend(cloud):
    cm = next(d for d in build(f"infrastructure/{cloud}/room-broker") if d["kind"] == "ConfigMap"
              and d["metadata"]["name"].startswith("room-broker-config"))
    return yaml.safe_load(cm["data"]["config.yaml"]).get("suspend") or {}


def factory_suspend(cloud):
    docs_ = build(f"tooling/{cloud}/agent-factory")
    release = next(d for d in docs_ if d["kind"] == "HelmRelease" and d["metadata"]["name"] == "agent-factory")
    cms = {d["metadata"]["name"]: d for d in docs_ if d["kind"] == "ConfigMap"}
    enabled = False
    for ref in release["spec"]["valuesFrom"]:  # Helm merges them in order, the last one wins
        sandbox = (yaml.safe_load(cms[ref["name"]]["data"]["values.yaml"])["config"].get("sandbox") or {})
        enabled = (sandbox.get("suspend") or {}).get("enabled", enabled)
    return enabled


checks = {}
for cluster in sorted((ROOT / "clusters").glob("*-agent-platform")):
    cloud = cluster.name.removesuffix("-agent-platform")
    on = cloud in ON
    listed = yaml.safe_load((cluster / "kustomization.yaml").read_text())["resources"]
    ks = cluster / "infrastructure-room-broker-suspend.yaml"
    checks[f"{cluster.name}: the suspend Kustomization exists"] = ks.is_file()
    checks[f"{cluster.name}: it is {'listed' if on else 'not listed'}"] = (ks.name in listed) == on
    broker = broker_suspend(cloud)
    checks[f"{cloud}: the broker's suspend is {'on, after 5m' if on else 'off'}"] = (
        broker == {"enabled": True, "after": "5m"} if on else not broker.get("enabled", False))
    checks[f"{cloud}: the factory's sandbox.suspend is {'on' if on else 'off'}"] = factory_suspend(cloud) == on
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
checks["base's broker config never enables suspend"] = not (config.get("suspend") or {}).get("enabled", False)
gcp = yaml.safe_load((ROOT / "infrastructure/gcp-0/room-broker/config.yaml").read_text())
checks["gcp-0's broker config is base's but for suspend"] = (
    {k: v for k, v in gcp.items() if k != "suspend"} == {k: v for k, v in config.items() if k != "suspend"})

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
