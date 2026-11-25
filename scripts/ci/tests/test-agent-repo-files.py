#!/usr/bin/env python3
# requires: python3
"""This repository as the agent factory's second repository (second-repository design D7, D9).

- No octo-sts trust policy: the factory mints each run's git token (R3), so none is served here.
- The fence names the live factory, the status page's activeCluster (aws-0 or gcp-0).
- Factory.spec.mergeGuardrails.protectedFiles is the gate list maku/merge-gate reads. Every sentinel
  below must match it, including the factory's own resources and the CI gates.

run-tests.sh runs this from .composite/ (the host's .github/ stays there) with cwd = this repo."""
import pathlib
import re
import sys

import yaml

OWN = pathlib.Path.cwd()
SENTINELS = [
    ".policy.yml", ".github/agent-factory.yaml", ".github/chainguard/agent-implementer.sts.yaml",
    ".github/workflows/ci.yaml", "AGENTS.md", ".claude/settings.json", ".agents/skills/x",
    "clusters/aws-0-agent-platform/kustomization.yaml", "flux/sources/ocirepo-agent-factory.yaml",
    "tooling/base/agent-factory/helm-values-configmap.yaml",
    "tooling/base/agent-factory/resources/mergepolicy-x.yaml",
    "tooling/aws-0/agent-factory/x", "infrastructure/base/agent-gateway/x",
    "infrastructure/aws-0/agent-gateway/x", "observability/base/agent-platform/x",
    "scripts/ci/flux-schema/assert-agent-gateway.py", "HOST_REF", "taskfile.yaml",
    ".pre-commit-config.yaml", ".secrets.baseline", ".github/agent-checks.yaml",
]
fails = []

if trust := sorted(p.name for p in (OWN / ".github/chainguard").glob("*.sts.yaml")):
    fails.append(f"octo-sts trust policies are retired, found {trust}")

STATUS_PAGE = "website/content/docs/status.md"
fence = OWN / ".github/agent-factory.yaml"
status = OWN / STATUS_PAGE
active = (yaml.safe_load(status.read_text().split("---")[1]) or {}).get("activeCluster") if status.is_file() else None
if active not in ("aws-0", "gcp-0"):
    fails.append(f"{STATUS_PAGE}: activeCluster must be aws-0 or gcp-0, got {active!r}")
elif not fence.is_file() or (yaml.safe_load(fence.read_text()) or {}) != {"factory": active}:
    fails.append(f".github/agent-factory.yaml: must be exactly `factory: {active}` (the status page's activeCluster)")

sys.path.insert(0, str(OWN / "scripts/ci"))
import factory_config  # the values file with the Factory, Repository and MergePolicy objects over it

config = factory_config.config(OWN)
gates = (config.get("mergeGuardrails") or {}).get("protectedFiles") or []
if not gates:
    fails.append("Factory.spec.mergeGuardrails.protectedFiles is unset")
for sentinel in SENTINELS:
    if not any(re.search(gate, sentinel) for gate in gates):
        fails.append(f"Factory.spec.mergeGuardrails.protectedFiles: sentinel {sentinel} is not a gate path")

# The Factory applies to the host too. Its former policy-bot-only paths live on every host binding,
# so neither a live policy nor a later promotion can bypass one.
HOST_SENTINELS = [
    "infrastructure/base/kueue/x", "infrastructure/aws-0/kueue/x",
    "infrastructure/base/crossplane/configuration-aws/x",
    "infrastructure/aws-0/crossplane/configuration/x", "flux/sources/ocirepo-kueue.yaml",
    "opentofu/aws/openbao/management/mounts.tf", "opentofu/aws/eks/configure/openbao.tf",
    "scripts/ci/check-policy-gate-coverage.sh", "docs/platform-constitution.md",
]
host = next(r for r in config["repositories"] if r["name"] == "Smana/cloud-native-ref")
for name, cl in sorted((host.get("classes") or {}).items()):
    protected = cl.get("protectedFiles") or []
    for sentinel in HOST_SENTINELS:
        if not any(re.search(gate, sentinel) for gate in protected):
            fails.append(f"cloud-native-ref policy {name}: host sentinel {sentinel} is not protected")

for failure in fails:
    print("FAIL", failure)
if fails:
    sys.exit(1)
print("PASS")
