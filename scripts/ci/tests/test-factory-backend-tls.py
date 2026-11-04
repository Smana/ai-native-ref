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
aws = (ROOT / "tooling/aws-0/agent-factory/kustomization.yaml").read_text()
if "configmap-agent-factory-ca.yaml" not in aws:
    problems.append("aws-0's agent-factory kustomization does not ship the CA ConfigMap")
# The host's copy for RunLore (cloud-native-ref, observability/aws-0/configmap-factory-ca.yaml) holds the same certificate,
# where the host clone is visible and carries it (after the HOST_REF bump).
for host in (ROOT / ".host", ROOT / ".composite"):
    other = host / "observability/aws-0/configmap-factory-ca.yaml"
    if other.exists():
        theirs = yaml.safe_load(other.read_text())["data"]["ca.crt"].split()
        if theirs != pem.split():
            problems.append(f"{other.relative_to(ROOT)} holds another certificate than agent-factory-ca: rotate both repositories together")
        break
if problems:
    print("\n".join(problems))
    sys.exit(1)
print("PASS: the tailnet route's BackendTLSPolicy matches the factory's TLS port, name and CA")
