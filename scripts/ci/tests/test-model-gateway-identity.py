#!/usr/bin/env python3
# requires: python3 kustomize
"""The model gateway's Google identity (Gemini design G1 to G3, plan B3).

  I1  gcp-0's model-gateway render holds exactly one GCPWorkloadIdentity, xplane-model-gateway in
      agent-gateway, for the proxy's ServiceAccount model-gateway (the Gateway's name, Maku
      docs/gateway.md), with the one prediction-only role ${gcp_vertex_predict_role}: never a key,
      never a predefined Vertex role, never a bucket role.
  I2  base and aws-0 hold none: only gcp-0 reaches Vertex AI.
  I3  The Flux child that applies it waits for crossplane-configuration, which installs the claim's
      CRD (HOST-CONTRACT H2).

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
child = yaml.safe_load((ROOT / "clusters/gcp-0-agent-platform/infrastructure-model-gateway.yaml").read_text())
if {"name": "crossplane-configuration"} not in child["spec"].get("dependsOn", []):
    problems.append("I3: the gcp-0 model-gateway child must dependsOn crossplane-configuration (the claim's CRD)")

for p in problems:
    print(p)
if problems:
    sys.exit(1)
print("PASS: the model gateway's Google identity")
