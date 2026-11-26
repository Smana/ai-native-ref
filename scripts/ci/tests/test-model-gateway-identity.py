#!/usr/bin/env python3
# requires: python3 kustomize
"""The model gateway's Google identity (Gemini design G1 to G3, plan B3).

  I1  gcp-0's model-gateway render holds exactly one GCPWorkloadIdentity, xplane-model-gateway in
      agent-gateway, for the proxy's ServiceAccount model-gateway (the Gateway's name, Maku
      docs/gateway.md), with the one prediction-only role ${gcp_vertex_predict_role}: never a key,
      never a predefined Vertex role, never a bucket role.
  I2  base and aws-0 hold none.
  I3  The Flux child that applies it waits for crossplane-configuration, which installs the claim's
      CRD (HOST-CONTRACT H2).
  I4  aws-0 reaches Vertex AI through Workload Identity Federation (cloud-native-ref's
      aws-vertex-federation design): exactly one EPI, xplane-model-gateway in agent-gateway, for
      agent-gateway/model-gateway, whose policy denies every action (the host's pool trusts the role
      by that name, H5); an external_account credential with an aws1 source on the loopback sidecar,
      never a key, never impersonation; its child waits for eks-pod-identities (the EPI's CRD).
  I5  The sidecar's one extra egress is the Pod Identity agent (host entity, port 80); base holds
      no EPI and no credential.

Run: python3 scripts/ci/tests/test-model-gateway-identity.py
"""
import pathlib
import subprocess
import sys

try:
    import yaml
except ImportError:
    print("SKIP: pyyaml not installed")
    sys.exit(77)

ROOT = pathlib.Path(__file__).resolve().parents[3]
problems = []


def render(path):
    out = subprocess.run(["kustomize", "build", str(ROOT / path)], capture_output=True, text=True, check=True).stdout
    return [d for d in yaml.safe_load_all(out) if isinstance(d, dict)]


claims = [d for d in render("infrastructure/gcp-0/agent-gateway/model-gateway") if d.get("kind") == "GCPWorkloadIdentity"]
want = {"apiVersion": "cloud.ogenki.io/v1alpha1", "kind": "GCPWorkloadIdentity",
        "metadata": {"name": "xplane-model-gateway", "namespace": "agent-gateway"},
        "spec": {"serviceAccount": {"name": "model-gateway"}, "roles": ["${gcp_vertex_predict_role}"]}}
if [{k: c.get(k) for k in want} for c in claims] != [want]:
    problems.append(f"I1: gcp-0 must hold exactly {want}, got {claims}")
for path in ("infrastructure/base/agent-gateway/model-gateway", "infrastructure/aws-0/agent-gateway/model-gateway"):
    if any(d.get("kind") == "GCPWorkloadIdentity" for d in render(path)):
        problems.append(f"I2: {path} renders a GCPWorkloadIdentity; only gcp-0 reaches Vertex AI")
import json

aws = render("infrastructure/aws-0/agent-gateway/model-gateway")
epis = [d for d in aws if d.get("kind") == "EPI"]
if [(e["metadata"]["name"], e["metadata"]["namespace"], e["spec"]["serviceAccount"]) for e in epis] != \
        [("xplane-model-gateway", "agent-gateway", {"name": "model-gateway", "namespace": "agent-gateway"})]:
    problems.append(f"I4: aws-0 must hold exactly EPI agent-gateway/xplane-model-gateway for model-gateway, got {epis}")
else:
    stmts = json.loads(epis[0]["spec"]["policyDocument"])["Statement"]
    if stmts != [{"Sid": "IdentityOnly", "Effect": "Deny", "Action": "*", "Resource": "*"}]:
        problems.append(f"I4: the EPI's policy must deny everything, got {stmts}")
cms = {d["metadata"]["name"]: d for d in aws if d.get("kind") == "ConfigMap"}
cred = json.loads(cms.get("model-gateway-gcp-credentials", {}).get("data", {}).get("credentials.json", "{}"))
src = cred.get("credential_source", {})
if cred.get("type") != "external_account" or cred.get("audience") != "${gcp_vertex_wif_audience}" \
        or cred.get("subject_token_type") != "urn:ietf:params:aws:token-type:aws4_request" \
        or src.get("environment_id") != "aws1" \
        or src.get("url") != "http://127.0.0.1:8099/latest/meta-data/iam/security-credentials" \
        or "service_account_impersonation_url" in cred or "private_key" in json.dumps(cred):
    problems.append(f"I4: aws-0's credential must be an aws1 external_account on the loopback sidecar, got {cred}")
if "server.py" not in cms.get("model-gateway-aws-creds", {}).get("data", {}):
    problems.append("I4: aws-0 must carry the aws-creds sidecar's server.py")
cnps = [d for d in aws if d.get("kind") == "CiliumNetworkPolicy" and d["metadata"]["name"] == "model-gateway-aws-creds"]
if [c["spec"].get("egress") for c in cnps] != [[{"toEntities": ["host"], "toPorts": [{"ports": [{"port": "80", "protocol": "TCP"}]}]}]] \
        or any("ingress" in c["spec"] for c in cnps):
    problems.append(f"I5: the sidecar's policy must add egress to the host on 80 and nothing else, got {cnps}")
base = render("infrastructure/base/agent-gateway/model-gateway")
if any(d.get("kind") == "EPI" or d.get("metadata", {}).get("name") == "model-gateway-gcp-credentials" for d in base):
    problems.append("I5: base holds the AWS identity or the Google credential; they are aws-0's")
awschild = yaml.safe_load((ROOT / "clusters/aws-0-agent-platform/infrastructure-model-gateway.yaml").read_text())
if {"name": "eks-pod-identities"} not in awschild["spec"].get("dependsOn", []):
    problems.append("I4: the aws-0 model-gateway child must dependsOn eks-pod-identities (the EPI's CRD)")

child = yaml.safe_load((ROOT / "clusters/gcp-0-agent-platform/infrastructure-model-gateway.yaml").read_text())
if {"name": "crossplane-configuration"} not in child["spec"].get("dependsOn", []):
    problems.append("I3: the gcp-0 model-gateway child must dependsOn crossplane-configuration (the claim's CRD)")

for p in problems:
    print(p)
if problems:
    sys.exit(1)
print("PASS: the model gateway's Google identity")
