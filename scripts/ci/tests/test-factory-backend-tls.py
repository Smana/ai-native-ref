#!/usr/bin/env python3
# requires: python3
"""The tailnet route reaches a TLS factory: the BackendTLSPolicy targets the Service port the chart names `https`, checks
the in-cluster name the factory's certificate carries, and trusts a ConfigMap an ExternalSecret writes from the same CA
as the broker's. Without it the gateway speaks plain HTTP to a TLS listener and the CLI's POST /v1/runs gets a 5xx."""
import pathlib
import sys

try:
    import yaml
except ImportError:
    print("PyYAML is not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
problems = []


def load(rel):
    return [d for d in yaml.safe_load_all((ROOT / rel).read_text()) if d]


policy = load("tooling/base/agent-factory/backendtlspolicy.yaml")[0]
route = load("tooling/base/agent-factory/httproute.yaml")[0]
values = yaml.safe_load(next(d for d in load("tooling/base/agent-factory/helm-values-configmap.yaml")
                             if d["kind"] == "ConfigMap")["data"]["values.yaml"])
cm = load("tooling/aws-0/agent-factory/configmap-agent-factory-ca.yaml")[0]
spec = policy["spec"]

if policy["apiVersion"] != "gateway.networking.k8s.io/v1":
    problems.append(f"BackendTLSPolicy apiVersion {policy['apiVersion']}: Gateway API v1.6 serves v1")
target = spec["targetRefs"]
backend = route["spec"]["rules"][0]["backendRefs"][0]
if len(target) != 1 or (target[0]["kind"], target[0]["name"]) != ("Service", backend["name"]):
    problems.append(f"the policy must target the route's Service {backend['name']}: {target}")
if target[0].get("sectionName") != "https" or not values["api"]["tls"].get("secretName"):
    problems.append("the policy targets the port named https, which the chart names only when api.tls.secretName is set")
if spec["validation"]["hostname"] != "agent-factory.agent-system.svc":
    problems.append(f"hostname {spec['validation']['hostname']} is not a name the factory certificate carries")
refs = spec["validation"]["caCertificateRefs"]
if [(r["kind"], r["name"]) for r in refs] != [("ConfigMap", cm["metadata"]["name"])]:
    problems.append(f"caCertificateRefs must name the ConfigMap aws-0 ships: {refs}")
if policy["metadata"]["namespace"] != cm["metadata"]["namespace"]:
    problems.append("the policy and its ConfigMap must share a namespace (no ReferenceGrant is shipped)")
pem = cm["data"].get("ca.crt", "")
if "BEGIN CERTIFICATE" not in pem or "PRIVATE KEY" in pem:
    problems.append("the ConfigMap's ca.crt must be a certificate, never a key")
for cloud in ("aws-0", "gcp-0"):
    kz = (ROOT / f"tooling/{cloud}/agent-factory/kustomization.yaml").read_text()
    if "configmap-agent-factory-ca.yaml" not in kz:
        problems.append(f"{cloud}'s agent-factory kustomization does not ship the CA ConfigMap")
    other = yaml.safe_load((ROOT / f"tooling/{cloud}/agent-factory/configmap-agent-factory-ca.yaml").read_text())
    if other["data"]["ca.crt"].split() != pem.split():
        problems.append(f"{cloud}'s agent-factory-ca differs from aws-0's: one offline root signs both, rotate them together")
# RunLore's values name the CA file the host mounts, as a sibling of /etc/runlore (a mount inside the chart's read-only
# config mount cannot be created). The host's mount and ConfigMaps are checked where the host clone carries them.
rl = yaml.safe_load(next(d for d in yaml.safe_load_all((ROOT / "observability/base/runlore-factory/helm-values-configmap.yaml")
                                                          .read_text()) if d)["data"]["values.yaml"])["config"]["factory"]
if rl.get("ca_file", "").startswith("/etc/runlore/"):
    problems.append(f"factory.ca_file {rl['ca_file']} is inside the chart's read-only /etc/runlore mount")
for host in (ROOT / ".host", ROOT / ".composite"):
    mount = host / "observability/base/runlore/helm-values-configmap.yaml"
    if mount.exists():
        hv = yaml.safe_load(next(d for d in yaml.safe_load_all(mount.read_text()) if d)["data"]["values.yaml"])
        paths = [m["mountPath"] for m in hv.get("extraVolumeMounts", []) if m["name"] == "factory-ca"]
        if paths and not rl.get("ca_file", "").startswith(paths[0] + "/"):
            problems.append(f"factory.ca_file {rl.get('ca_file')} is not under the host's factory-ca mount {paths[0]}")
        if paths and (paths[0] == "/etc/runlore" or paths[0].startswith("/etc/runlore/")):
            problems.append(f"the host mounts factory-ca at {paths[0]}, inside the chart's read-only /etc/runlore")
    for rel in ("observability/aws-0/configmap-factory-ca.yaml", "observability/gcp-0/runlore/configmap-factory-ca.yaml"):
        theirs = host / rel
        if theirs.exists() and yaml.safe_load(theirs.read_text())["data"]["ca.crt"].split() != pem.split():
            problems.append(f"{theirs.relative_to(ROOT)} holds another certificate than agent-factory-ca: rotate both repositories together")
if problems:
    print("\n".join(problems))
    sys.exit(1)
print("PASS: the tailnet route's BackendTLSPolicy matches the factory's TLS port, name and CA")
